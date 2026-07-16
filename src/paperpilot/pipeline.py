"""
End-to-end document processing and retrieval pipeline.

This module orchestrates the full flow from raw PDF to searchable knowledge:

    PDF → Extract → Chunk → Embed → Store → (ready for retrieval)

And the retrieval flow:

    Query → Embed → Search → Ranked Results

Why a pipeline module?
    Without it, the caller would need to manually wire together the extractor,
    chunker, embedder, and vector store — managing intermediate data, ensuring
    the right models are loaded, and handling errors at each step. The pipeline
    encapsulates this complexity behind a simple interface.

    This is the Facade pattern: a simplified interface to a complex subsystem.
    Each component (extractor, chunker, embedder, store) remains independently
    testable and swappable, but the pipeline provides a convenient entry point
    for common workflows.

Design decisions:
    - Dependencies are injected (EmbeddingEngine, FAISSVectorStore) rather than
      created internally. This makes testing easy (pass mocks) and allows
      sharing a single engine/store across multiple pipeline calls.
    - The pipeline does NOT own the vector store lifecycle. The caller creates,
      saves, and loads stores. The pipeline just adds to them and searches them.
    - Processing and retrieval are separate methods — you process once, then
      query many times.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from paperpilot.config import get_settings
from paperpilot.core.models import (
    PaperMetadata,
    ProcessedDocument,
    RetrievalResult,
    TextChunk,
)
from paperpilot.document.chunker import chunk_text
from paperpilot.document.extractor import extract_text_from_pdf, get_full_text
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


class DocumentPipeline:
    """Orchestrates document processing: PDF → Extract → Chunk → Embed → Store.

    This pipeline takes a PDF file and produces a fully processed document
    with its chunks embedded and stored in a vector index.

    The pipeline holds references to the embedding engine and vector store,
    and also maintains an in-memory chunk registry so that retrieval results
    can be resolved back to full TextChunk objects.

    Attributes:
        engine: The embedding engine used for generating vectors.
        store: The FAISS vector store where embeddings are indexed.

    Usage:
        engine = EmbeddingEngine()
        store = FAISSVectorStore(dimension=engine.embedding_dim)
        pipeline = DocumentPipeline(engine, store)

        # Process a paper
        doc = pipeline.process_pdf(Path("paper.pdf"))

        # Query it
        results = pipeline.retrieve("What is attention?")
    """

    def __init__(
        self,
        engine: EmbeddingEngine,
        store: FAISSVectorStore,
    ) -> None:
        """Initialize the pipeline with its dependencies.

        Args:
            engine: The embedding engine to use for vectorization.
            store: The vector store to index embeddings into.
        """
        self.engine = engine
        self.store = store

        # In-memory registry: chunk_id (str) → TextChunk
        # This lets us resolve FAISS search results back to full chunk objects
        # with all their metadata (text, page numbers, etc.).
        self._chunk_registry: dict[str, TextChunk] = {}

    def process_pdf(
        self,
        pdf_path: Path | str,
        metadata: PaperMetadata | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> ProcessedDocument:
        """Process a PDF through the full pipeline.

        Steps:
        1. Extract text from PDF (page by page)
        2. Concatenate into full text
        3. Chunk the text with overlap
        4. Embed all chunks
        5. Add embeddings to the vector store
        6. Register chunks for later retrieval

        Args:
            pdf_path: Path to the PDF file.
            metadata: Optional paper metadata. If not provided, a minimal
                      metadata object is created with the filename as title.
            chunk_size: Override the default chunk size from settings.
            chunk_overlap: Override the default chunk overlap from settings.

        Returns:
            A fully populated ProcessedDocument.
        """
        pdf_path = Path(pdf_path)
        settings = get_settings()

        # Use provided values or fall back to settings
        chunk_size = chunk_size or settings.chunk_size
        chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Create minimal metadata if none provided
        if metadata is None:
            metadata = PaperMetadata(title=pdf_path.stem)

        logger.info("Processing PDF: %s", pdf_path.name)

        # Step 1: Extract text
        pages = extract_text_from_pdf(pdf_path)
        full_text = get_full_text(pages)
        logger.info("Extracted %d pages, %d characters", len(pages), len(full_text))

        # Step 2: Chunk the text
        chunks = chunk_text(
            text=full_text,
            paper_id=metadata.paper_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            pages=pages,
        )
        logger.info("Created %d chunks", len(chunks))

        # Step 3: Embed all chunks
        chunk_texts = [c.text for c in chunks]
        embeddings = self.engine.embed_texts(chunk_texts)
        logger.info("Generated embeddings of shape %s", embeddings.shape)

        # Step 4: Add to vector store
        chunk_ids = [c.chunk_id for c in chunks]
        self.store.add(embeddings, chunk_ids)

        # Step 5: Register chunks for retrieval resolution
        for chunk in chunks:
            self._chunk_registry[str(chunk.chunk_id)] = chunk

        # Build and return the processed document
        doc = ProcessedDocument(
            metadata=metadata,
            source_path=pdf_path,
            full_text=full_text,
            pages=pages,
            chunks=chunks,
            total_pages=len(pages),
            total_chars=len(full_text),
        )

        logger.info(
            "Pipeline complete for '%s': %d pages, %d chunks indexed",
            metadata.title,
            doc.total_pages,
            len(chunks),
        )

        return doc

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve the most relevant chunks for a natural language query.

        Steps:
        1. Embed the query using the same model used for chunks
        2. Search the FAISS index for nearest neighbors
        3. Resolve FAISS indices back to TextChunk objects
        4. Return ranked RetrievalResult objects

        Args:
            query: Natural language query string.
            top_k: Number of results to return. Defaults to settings value.

        Returns:
            A list of RetrievalResult objects sorted by relevance (most
            relevant first). Each result contains the chunk text, similarity
            score, and rank.
        """
        settings = get_settings()
        top_k = top_k or settings.retrieval_top_k

        logger.info("Retrieving for query: '%s' (top_k=%d)", query, top_k)

        # Step 1: Embed the query
        query_vector = self.engine.embed_query(query)

        # Step 2: Search the vector store
        search_results = self.store.search(query_vector, k=top_k)

        # Step 3: Resolve to RetrievalResult objects
        results: list[RetrievalResult] = []
        for rank, (chunk_id_str, distance) in enumerate(search_results, start=1):
            chunk = self._chunk_registry.get(chunk_id_str)
            if chunk is None:
                logger.warning(
                    "Chunk ID %s not found in registry (may not have been "
                    "processed in this session)",
                    chunk_id_str,
                )
                continue

            result = RetrievalResult(
                chunk=chunk,
                score=distance,
                rank=rank,
            )
            results.append(result)

        logger.info("Retrieved %d results", len(results))
        return results
