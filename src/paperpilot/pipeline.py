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
from paperpilot.agent.tutor import TutorAgent
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
from paperpilot.workspace.manager import WorkspaceManager

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
        tutor: The TutorAgent used to answer grounded questions.

    Usage:
        engine = EmbeddingEngine()
        store = FAISSVectorStore(dimension=engine.embedding_dim)
        tutor = TutorAgent(chat_model=ChatOpenAI(...))
        pipeline = DocumentPipeline(engine, store, tutor)

        # Process a paper
        doc = pipeline.process_pdf(Path("paper.pdf"))

        # Query it (Retrieval-only)
        results = pipeline.retrieve("What is attention?")

        # Ask a question (Grounded RAG Answer)
        answer = pipeline.answer_question("How does self-attention work?")
    """

    def __init__(
        self,
        engine: EmbeddingEngine,
        store: FAISSVectorStore,
        tutor: TutorAgent | None = None,
        db_manager: WorkspaceManager | None = None,
        workspace_id: UUID | None = None,
    ) -> None:
        """Initialize the pipeline with its dependencies.

        Args:
            engine: The embedding engine to use for vectorization.
            store: The vector store to index embeddings into.
            tutor: Optional TutorAgent for answering questions.
            db_manager: Optional WorkspaceManager for workspace storage.
            workspace_id: Optional UUID of the active workspace.
        """
        self.engine = engine
        self.store = store
        self.tutor = tutor
        self.db_manager = db_manager
        self.workspace_id = workspace_id

        # In-memory registry: chunk_id (str) → TextChunk
        # This lets us resolve FAISS search results back to full chunk objects
        # with all their metadata (text, page numbers, etc.).
        self._chunk_registry: dict[str, TextChunk] = {}

        # Initialize downloader and sync providers
        from paperpilot.document.downloader import PDFDownloader
        from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
        settings = get_settings()
        self.downloader = PDFDownloader(papers_dir=settings.papers_dir)
        self.arxiv_provider = ArxivProvider()
        self.semantic_scholar_provider = SemanticScholarProvider()

        # If a workspace is specified, load it
        if self.workspace_id and self.db_manager:
            self.load_workspace(self.workspace_id)

    def load_workspace(self, workspace_id: UUID) -> None:
        """Load workspace chunks into the registry and restore its consolidated FAISS index.

        Args:
            workspace_id: The workspace UUID.
        """
        if not self.db_manager:
            raise ValueError("WorkspaceManager must be configured in DocumentPipeline to load a workspace.")

        self.workspace_id = workspace_id

        # 1. Fetch chunks and populate chunk registry
        chunks = self.db_manager.get_chunks_for_workspace(workspace_id)
        self._chunk_registry.clear()
        for chunk in chunks:
            self._chunk_registry[str(chunk.chunk_id)] = chunk

        # 2. Restore consolidated FAISS index
        settings = get_settings()
        workspace_index_dir = settings.index_dir / f"workspace_{workspace_id}"

        if (workspace_index_dir / "index.faiss").exists():
            logger.info("Loading existing workspace FAISS index from %s", workspace_index_dir)
            self.store = FAISSVectorStore.load(workspace_index_dir)
        else:
            logger.info("No existing workspace FAISS index found at %s. Initializing empty index.", workspace_index_dir)
            self.store = FAISSVectorStore(dimension=self.engine.embedding_dim)

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

        # Step 6: Save to workspace database if configured
        if self.workspace_id and self.db_manager:
            # Save paper metadata and chunks to SQLite database
            self.db_manager.add_paper_to_workspace(self.workspace_id, metadata, chunks)

            # Persist consolidated FAISS index to disk
            settings = get_settings()
            workspace_index_dir = settings.index_dir / f"workspace_{self.workspace_id}"
            self.store.save(workspace_index_dir)
            logger.info("Persisted workspace FAISS index to %s", workspace_index_dir)

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

    def answer_question(
        self,
        query: str,
        top_k: int | None = None,
        difficulty: str = "graduate/expert",
    ) -> str:
        """Answer a user question grounded in retrieved document context.

        Steps:
        1. Retrieve the top-K relevant chunks for the query.
        2. Extract the TextChunk objects from the results.
        3. Invoke the TutorAgent to answer the question using the chunks.

        Args:
            query: The user's natural language question.
            top_k: Number of chunks to retrieve for context. Defaults to settings.
            difficulty: Explanation difficulty level ('beginner', 'undergraduate', 'graduate/expert').

        Returns:
            The textual answer generated by the LLM.

        Raises:
            ValueError: If the Tutor Agent has not been injected into the pipeline.
        """
        if self.tutor is None:
            raise ValueError(
                "Tutor Agent has not been configured in this pipeline. "
                "Please initialize DocumentPipeline with a TutorAgent."
            )

        logger.info("Answering question: '%s'", query)

        # Step 1: Retrieve context
        retrieval_results = self.retrieve(query, top_k=top_k)

        # Step 2: Extract raw TextChunks
        chunks = [result.chunk for result in retrieval_results]

        # Step 3: Generate grounded answer via tutor agent
        answer = self.tutor.answer_question(query, chunks, difficulty=difficulty)

        return answer

    def download_and_process_pdf(
        self,
        paper_id: UUID,
        pdf_url: str,
        metadata: PaperMetadata | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> ProcessedDocument:
        """Download a PDF file from a URL, then process and index it in the pipeline."""
        logger.info("Downloading and processing PDF for paper %s from %s", paper_id, pdf_url)
        local_path = self.downloader.download_pdf(paper_id, pdf_url)

        if metadata:
            metadata.paper_id = paper_id

        return self.process_pdf(
            local_path,
            metadata=metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def sync_paper_metadata(self, paper_id: UUID) -> PaperMetadata:
        """Sync and update paper metadata from external providers (arXiv/Semantic Scholar)."""
        if not self.db_manager:
            raise ValueError("WorkspaceManager must be configured in DocumentPipeline to sync metadata.")

        # 1. Fetch current paper metadata from database
        papers = self.db_manager.get_workspace_papers(self.workspace_id)
        current_paper = next((p for p in papers if p.paper_id == paper_id), None)
        if not current_paper:
            # Check if paper exists generally in the papers table
            with self.db_manager._get_connection() as conn:
                row = conn.execute("SELECT * FROM papers WHERE paper_id = ?;", (str(paper_id),)).fetchone()
                if not row:
                    raise ValueError(f"Paper with ID {paper_id} not found in database.")
                import json
                from datetime import datetime
                from paperpilot.core.models import PaperSource
                current_paper = PaperMetadata(
                    paper_id=UUID(row["paper_id"]),
                    title=row["title"],
                    authors=json.loads(row["authors"]) if row["authors"] else [],
                    publication_year=row["publication_year"],
                    citation_count=row["citation_count"],
                    abstract=row["abstract"],
                    doi=row["doi"],
                    pdf_url=row["pdf_url"],
                    source=PaperSource(row["source"]),
                    venue=row["venue"],
                    keywords=json.loads(row["keywords"]) if row["keywords"] else [],
                    discovered_at=datetime.fromisoformat(row["discovered_at"]),
                )

        logger.info("Syncing metadata for paper: '%s'", current_paper.title)

        # 2. Extract identifiers (ArXiv ID or DOI)
        import re
        arxiv_id = None
        # Check keywords
        if current_paper.keywords:
            for kw in current_paper.keywords:
                if kw != "arxiv" and kw != "semanticscholar" and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", kw):
                    arxiv_id = kw.split("v")[0]
                    break
        # Check URL
        if not arxiv_id and current_paper.pdf_url and "arxiv.org" in current_paper.pdf_url:
            match = re.search(r"/pdf/(\d{4}\.\d{4,5})", current_paper.pdf_url)
            if match:
                arxiv_id = match.group(1)
            else:
                match = re.search(r"/abs/(\d{4}\.\d{4,5})", current_paper.pdf_url)
                if match:
                    arxiv_id = match.group(1)

        refreshed_meta = None

        # 3. Fetch latest from providers
        # First priority: Semantic Scholar via DOI
        if current_paper.doi:
            logger.info("Attempting Semantic Scholar metadata sync using DOI: %s", current_paper.doi)
            refreshed_meta = self.semantic_scholar_provider.get_paper_by_doi(current_paper.doi)

        # Second priority: Semantic Scholar via ArXiv ID
        if not refreshed_meta and arxiv_id:
            logger.info("Attempting Semantic Scholar metadata sync using ArXiv ID: %s", arxiv_id)
            refreshed_meta = self.semantic_scholar_provider.get_paper_by_arxiv(arxiv_id)

        # Third priority: ArXiv via ArXiv ID
        if not refreshed_meta and arxiv_id:
            logger.info("Attempting ArXiv metadata sync using ArXiv ID: %s", arxiv_id)
            refreshed_meta = self.arxiv_provider.get_paper_by_id(arxiv_id)

        if not refreshed_meta:
            logger.warning("Could not retrieve refreshed metadata from providers for: '%s'", current_paper.title)
            return current_paper

        # 4. Update fields on current paper
        current_paper.title = refreshed_meta.title or current_paper.title
        current_paper.authors = refreshed_meta.authors or current_paper.authors
        current_paper.publication_year = refreshed_meta.publication_year or current_paper.publication_year
        current_paper.citation_count = refreshed_meta.citation_count or current_paper.citation_count
        current_paper.abstract = refreshed_meta.abstract or current_paper.abstract
        current_paper.doi = refreshed_meta.doi or current_paper.doi
        current_paper.pdf_url = refreshed_meta.pdf_url or current_paper.pdf_url
        current_paper.venue = refreshed_meta.venue or current_paper.venue

        # Merge keywords
        merged_kws = list(set(current_paper.keywords + refreshed_meta.keywords))
        current_paper.keywords = merged_kws

        # 5. Persist to database
        self.db_manager.update_paper_metadata(current_paper)
        return current_paper


