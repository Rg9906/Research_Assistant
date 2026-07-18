"""Production-grade PaperSession and PaperSessionManager powering PaperPilot AI.

Utilizes native LlamaIndex abstractions for document loading, transformations,
indexing, storage persistence, reranking, and grounded QA.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from uuid import UUID

import llama_index.core
from llama_index.core import (
    Document,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
    Settings as LlamaSettings,
)
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.llms import ChatMessage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeWithScore, QueryBundle

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata
from paperpilot.document.downloader import PDFDownloader
from paperpilot.services.paper_chat.exceptions import (
    IndexBuildError,
    PDFDownloadError,
    PDFParseError,
    QueryExecutionError,
)

logger = logging.getLogger(__name__)


def compute_pdf_sha256(file_path: Path) -> str:
    """Calculate SHA256 checksum of a PDF file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _extract_source_nodes(response: Any, default_paper_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
    """Build structured citation dicts from a LlamaIndex response's source_nodes.

    Shared by PaperSession (single-paper chat/query) and
    PaperSessionManager.chat_across_papers (multi-paper chat), since both
    need to turn `response.source_nodes` into the same citation shape. Each
    node's own `paper_id` metadata (set in `_parse_pdf`) is preferred so
    multi-paper results are attributed to the paper they actually came from;
    `default_paper_id` is only a fallback for single-paper callers.
    """
    sources = []
    source_nodes = getattr(response, "source_nodes", []) or []
    for rank, node_with_score in enumerate(source_nodes, start=1):
        node = node_with_score.node
        meta = node.metadata or {}
        page_num = meta.get("page_label") or meta.get("page_number") or meta.get("page")
        paper_id = meta.get("paper_id") or (str(default_paper_id) if default_paper_id else None)

        sources.append({
            "rank": rank,
            "node_id": node.node_id,
            "score": float(node_with_score.score or 0.0),
            "text": node.get_content(),
            "page_number": str(page_num) if page_num is not None else "N/A",
            "filename": meta.get("file_name") or meta.get("filename") or (f"{paper_id}.pdf" if paper_id else "unknown.pdf"),
            "paper_id": paper_id,
            "metadata": meta,
        })
    return sources


class MultiPaperRetriever(BaseRetriever):
    """Merges top-k retrieval results across several papers' independent indexes.

    Each paper is indexed into its own VectorStoreIndex (see
    PaperSessionManager.get_or_create_session), so there is no single index
    spanning a whole workspace. For multi-paper workspace chat, this
    retriever queries every paper's index independently and merges the
    results by similarity score, giving a single ranked context list that
    can span multiple papers.
    """

    def __init__(self, sessions: List["PaperSession"], similarity_top_k: int = 5) -> None:
        self._sessions = sessions
        self._similarity_top_k = max(1, similarity_top_k)
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        all_nodes: List[NodeWithScore] = []
        for session in self._sessions:
            retriever = session.index.as_retriever(similarity_top_k=self._similarity_top_k)
            all_nodes.extend(retriever.retrieve(query_bundle))

        all_nodes.sort(key=lambda n: n.score or 0.0, reverse=True)
        return all_nodes[: self._similarity_top_k]


class PaperSession:
    """Production-grade PaperSession encapsulating document intelligence for a paper.

    Sole interface used by the rest of the application.
    Exposes: chat(), query(), stream(), get_sources(), get_metadata().
    """

    def __init__(
        self,
        metadata: PaperMetadata,
        paper_dir: Path,
        index: VectorStoreIndex,
    ) -> None:
        self.metadata = metadata
        self.paper_id = metadata.paper_id
        self.paper_dir = paper_dir
        self.index = index
        self.settings = get_settings()
        self._last_sources: List[Dict[str, Any]] = []
        self._last_chat_history: List[ChatMessage] = []

        # Configure node postprocessors: similarity cutoff first (drops
        # chunks that aren't actually relevant before spending compute on
        # reranking), then the optional reranker.
        self._node_postprocessors = []
        if self.settings.rag_similarity_threshold > 0:
            from llama_index.core.postprocessor import SimilarityPostprocessor
            self._node_postprocessors.append(
                SimilarityPostprocessor(similarity_cutoff=self.settings.rag_similarity_threshold)
            )

        if self.settings.rag_rerank_enabled:
            try:
                from llama_index.core.postprocessor import SentenceTransformerRerank
                start_time = time.time()
                reranker = SentenceTransformerRerank(
                    model=self.settings.rag_rerank_model,
                    top_n=self.settings.rag_rerank_top_n,
                )
                self._node_postprocessors.append(reranker)
                logger.info(
                    "Reranker executed setup for %s in %.3fs",
                    self.settings.rag_rerank_model,
                    time.time() - start_time,
                )
            except Exception as e:
                logger.warning("Could not initialize LlamaIndex Reranker: %s", e)

    def _build_chat_engine(self, chat_history: Optional[List[ChatMessage]] = None) -> Any:
        """Construct a fresh LlamaIndex chat engine seeded with the given history.

        A PaperSession (and the index it wraps) is cached and shared by
        PaperSessionManager across every caller asking about this paper — that
        sharing is desirable, since the index is expensive to build and purely
        read-only for retrieval. Conversation memory is not: a single chat
        engine instance stored on `self` would accumulate every caller's
        messages into one buffer, so unrelated workspaces/users discussing the
        same paper would see each other's conversation history. Building a new
        engine per call, seeded only with the caller-supplied history, keeps
        the shared index but scopes memory to whoever passed in that history.
        """
        return self.index.as_chat_engine(
            chat_mode="condense_plus_context",
            similarity_top_k=self.settings.rag_top_k,
            node_postprocessors=self._node_postprocessors,
            chat_history=chat_history or [],
        )

    def _extract_source_nodes(self, response: Any) -> List[Dict[str, Any]]:
        """Extract structured citations and metadata from LlamaIndex source_nodes."""
        sources = _extract_source_nodes(response, default_paper_id=self.paper_id)
        self._last_sources = sources
        return sources

    def chat(self, message: str, chat_history: Optional[List[ChatMessage]] = None) -> str:
        """Send a natural language message to the paper's chat engine and return the answer.

        `chat_history` seeds this turn's memory; it should be the value
        previously returned by `get_last_chat_history()` for whichever
        conversation (e.g. workspace) is calling. Omitting it starts a fresh,
        memory-less conversation rather than resuming someone else's — see
        `_build_chat_engine` for why memory isn't stored on `self`.
        """
        start_time = time.time()
        try:
            logger.info("Chat requested for paper '%s': '%s'", self.metadata.title, message)
            chat_engine = self._build_chat_engine(chat_history=chat_history)
            response = chat_engine.chat(message)
            self._extract_source_nodes(response)
            self._last_chat_history = chat_engine.chat_history
            logger.info(
                "LLM latency: %.3fs for paper '%s' (sources=%d)",
                time.time() - start_time,
                self.metadata.title,
                len(self._last_sources),
            )
            return str(response)
        except Exception as e:
            logger.error("Error executing chat for paper %s: %s", self.paper_id, e)
            raise QueryExecutionError(f"Failed to query paper '{self.metadata.title}': {e}") from e

    def get_last_chat_history(self) -> List[ChatMessage]:
        """Return the message history (post-memory-pruning) from the most recent chat()/stream() call.

        Callers that want multi-turn conversation must capture this after
        each call and pass it back in as `chat_history` on the next one.
        """
        return self._last_chat_history

    def query(self, query_str: str) -> str:
        """Execute a single-shot grounded query against the paper index."""
        start_time = time.time()
        try:
            query_engine = self.index.as_query_engine(
                similarity_top_k=self.settings.rag_top_k,
                node_postprocessors=self._node_postprocessors,
            )
            logger.info("Retriever executed query for paper '%s': '%s'", self.metadata.title, query_str)
            response = query_engine.query(query_str)
            self._extract_source_nodes(response)
            logger.info("LLM latency: %.3fs for query on paper '%s'", time.time() - start_time, self.metadata.title)
            return str(response)
        except Exception as e:
            logger.error("Error executing query for paper %s: %s", self.paper_id, e)
            raise QueryExecutionError(f"Failed to execute query: {e}") from e

    def stream(self, message: str, chat_history: Optional[List[ChatMessage]] = None) -> Generator[str, None, None]:
        """Stream response tokens from a fresh chat engine seeded with `chat_history`.

        See `chat()` for why history must be passed explicitly rather than
        relying on session-level state.
        """
        try:
            chat_engine = self._build_chat_engine(chat_history=chat_history)
            streaming_response = chat_engine.stream_chat(message)
            for token in streaming_response.response_gen:
                yield token
            self._extract_source_nodes(streaming_response)
            self._last_chat_history = chat_engine.chat_history
        except Exception as e:
            logger.error("Error streaming response for paper %s: %s", self.paper_id, e)
            raise QueryExecutionError(f"Failed to stream response: {e}") from e

    def get_sources(self) -> List[Dict[str, Any]]:
        """Return structured source nodes/citations from the most recent interaction."""
        return self._last_sources

    def get_metadata(self) -> PaperMetadata:
        """Return PaperMetadata for this session."""
        return self.metadata


class PaperSessionManager:
    """Manages index lifecycle, directory layout, fingerprinting, and session caching."""

    def __init__(self, downloader: PDFDownloader | None = None) -> None:
        self.settings = get_settings()
        self.base_dir = self.settings.storage_papers_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.downloader = downloader or PDFDownloader(papers_dir=self.settings.papers_dir)
        self._active_sessions: Dict[str, PaperSession] = {}
        self._configure_llama_defaults()

    def _configure_llama_defaults(self) -> None:
        """Configure LlamaIndex embedding and LLM defaults centrally from Settings."""
        api_key = os.environ.get("OPENAI_API_KEY") or self.settings.openai_api_key

        # 1. Embedding Model
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=self.settings.rag_embedding_model)
            logger.info("Configured LlamaIndex HuggingFaceEmbedding (%s)", self.settings.rag_embedding_model)
        except Exception as e:
            logger.warning("Could not load configured embedding model '%s': %s", self.settings.rag_embedding_model, e)

        # 2. LLM Model
        if api_key:
            try:
                from llama_index.llms.openai import OpenAI
                LlamaSettings.llm = OpenAI(
                    model=self.settings.rag_llm_model,
                    temperature=self.settings.llm_temperature,
                    api_key=api_key,
                )
                logger.info("Configured LlamaIndex OpenAI LLM (%s)", self.settings.rag_llm_model)
            except Exception as e:
                logger.warning("Could not initialize OpenAI LLM: %s", e)

    def _get_paper_dir(self, paper_id: UUID | str) -> Path:
        """Storage Layout: storage/papers/paper_<paper_id>/."""
        p_dir = self.base_dir / f"paper_{paper_id}"
        (p_dir / "index").mkdir(parents=True, exist_ok=True)
        (p_dir / "cache").mkdir(parents=True, exist_ok=True)
        return p_dir

    def _get_current_fingerprint(self, pdf_path: Path) -> Dict[str, Any]:
        """Generate a complete fingerprint for validating index cache freshness."""
        return {
            "pdf_sha256": compute_pdf_sha256(pdf_path),
            "embedding_model": self.settings.rag_embedding_model,
            "chunk_size": self.settings.rag_chunk_size,
            "chunk_overlap": self.settings.rag_chunk_overlap,
            "llama_index_version": getattr(llama_index.core, "__version__", "0.10.0"),
        }

    def _is_fingerprint_valid(self, paper_dir: Path, current_fingerprint: Dict[str, Any]) -> bool:
        """Check if index directory contains a matching fingerprint."""
        fingerprint_file = paper_dir / "fingerprint.json"
        index_dir = paper_dir / "index"
        docstore = index_dir / "docstore.json"
        
        if not fingerprint_file.exists() or not docstore.exists():
            return False

        try:
            with open(fingerprint_file, "r", encoding="utf-8") as f:
                saved_fingerprint = json.load(f)
            return saved_fingerprint == current_fingerprint
        except Exception as e:
            logger.warning("Failed to read fingerprint from %s: %s", fingerprint_file, e)
            return False

    def _parse_pdf(self, pdf_path: Path, metadata: PaperMetadata) -> List[Document]:
        """Parse PDF using PyMuPDFReader (preferred default) or fallback."""
        start_time = time.time()
        documents: List[Document] = []

        try:
            from llama_index.readers.file import PyMuPDFReader
            reader = PyMuPDFReader()
            documents = reader.load_data(file_path=str(pdf_path))
            logger.info("PDF parsed with PyMuPDFReader: %s (%d pages) in %.3fs", pdf_path.name, len(documents), time.time() - start_time)
        except Exception as e:
            logger.warning("PyMuPDFReader failed for %s: %s. Trying SimpleDirectoryReader fallback.", pdf_path.name, e)
            try:
                from llama_index.core import SimpleDirectoryReader
                documents = SimpleDirectoryReader(input_files=[str(pdf_path)]).load_data()
                logger.info("PDF parsed with SimpleDirectoryReader fallback: %s in %.3fs", pdf_path.name, time.time() - start_time)
            except Exception as parse_err:
                raise PDFParseError(f"Failed to parse PDF file '{pdf_path.name}': {parse_err}") from parse_err

        if not documents:
            raise PDFParseError(f"Parsed PDF '{pdf_path.name}' yielded 0 document pages.")

        authors_str = ", ".join(metadata.authors) if isinstance(metadata.authors, list) else str(metadata.authors or "")
        for doc in documents:
            doc.metadata.update({
                "paper_id": str(metadata.paper_id),
                "title": metadata.title,
                "authors": authors_str,
                "publication_year": metadata.publication_year or "",
                "doi": metadata.doi or "",
                "venue": metadata.venue or "",
                "filename": pdf_path.name,
            })

        return documents

    def get_or_create_session(
        self,
        metadata: PaperMetadata,
        pdf_url: str | None = None,
    ) -> PaperSession:
        """Obtain a PaperSession, reusing cached disk index or rebuilding automatically."""
        paper_id_str = str(metadata.paper_id)
        if paper_id_str in self._active_sessions:
            logger.info("Returning active in-memory PaperSession for paper %s", paper_id_str)
            return self._active_sessions[paper_id_str]

        paper_dir = self._get_paper_dir(metadata.paper_id)
        index_dir = paper_dir / "index"

        # 1. Ensure PDF is downloaded locally
        url_to_use = pdf_url or metadata.pdf_url
        if not url_to_use:
            raise PDFDownloadError(f"No PDF URL available for paper '{metadata.title}'")

        try:
            start_dl = time.time()
            pdf_path = self.downloader.download_pdf(paper_id=metadata.paper_id, pdf_url=url_to_use)
            logger.info("PDF downloaded/verified in %.3fs at %s", time.time() - start_dl, pdf_path)
        except Exception as e:
            raise PDFDownloadError(f"Failed to download PDF for paper '{metadata.title}': {e}") from e

        # 2. Check fingerprint freshness
        current_fingerprint = self._get_current_fingerprint(pdf_path)

        if self._is_fingerprint_valid(paper_dir, current_fingerprint):
            try:
                start_load = time.time()
                logger.info("Index fingerprint matched for paper %s. Loading from disk %s", paper_id_str, index_dir)
                storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
                index = load_index_from_storage(storage_context)
                logger.info("Index loaded in %.3fs for paper %s", time.time() - start_load, paper_id_str)
            except Exception as e:
                logger.warning("Failed to load existing index from %s: %s. Rebuilding.", index_dir, e)
                index = None
        else:
            logger.info("Fingerprint mismatch or missing index for paper %s. Rebuilding index.", paper_id_str)
            index = None

        # 3. Build index if needed
        if index is None:
            documents = self._parse_pdf(pdf_path, metadata)

            try:
                start_build = time.time()
                splitter = SentenceSplitter(
                    chunk_size=self.settings.rag_chunk_size,
                    chunk_overlap=self.settings.rag_chunk_overlap,
                )

                logger.info(
                    "Chunks created using SentenceSplitter (chunk_size=%d, overlap=%d)",
                    self.settings.rag_chunk_size,
                    self.settings.rag_chunk_overlap,
                )

                start_embed = time.time()
                index = VectorStoreIndex.from_documents(documents, transformations=[splitter])
                logger.info("Embedding completed in %.3fs", time.time() - start_embed)

                # Persist Index
                index.storage_context.persist(persist_dir=str(index_dir))
                logger.info("Index persisted in %.3fs to %s", time.time() - start_build, index_dir)

                # Persist Metadata & Fingerprint
                with open(paper_dir / "metadata.json", "w", encoding="utf-8") as f:
                    json.dump(metadata.model_dump(mode="json"), f, indent=2)

                with open(paper_dir / "fingerprint.json", "w", encoding="utf-8") as f:
                    json.dump(current_fingerprint, f, indent=2)

            except Exception as e:
                raise IndexBuildError(f"Failed to build LlamaIndex for paper '{metadata.title}': {e}") from e

        session = PaperSession(metadata=metadata, paper_dir=paper_dir, index=index)
        self._active_sessions[paper_id_str] = session
        return session

    def chat_across_papers(
        self,
        papers: List[PaperMetadata],
        message: str,
        chat_history: Optional[List[ChatMessage]] = None,
        similarity_top_k: Optional[int] = None,
    ) -> tuple[str, List[Dict[str, Any]], List[ChatMessage]]:
        """Chat grounded in the union of multiple papers' indexes.

        Each paper still has its own independently-built VectorStoreIndex
        (see get_or_create_session), so this fans a single query out across
        every paper's retriever via MultiPaperRetriever and merges results by
        score before generation, rather than only ever answering from the
        first paper in a workspace.

        Returns (answer, source_citations, updated_chat_history) — callers own
        persisting chat_history across turns, same contract as PaperSession.chat().
        """
        if not papers:
            raise ValueError("chat_across_papers requires at least one paper.")

        sessions = [
            self.get_or_create_session(metadata=paper, pdf_url=paper.pdf_url) for paper in papers
        ]

        if len(sessions) == 1:
            answer = sessions[0].chat(message, chat_history=chat_history)
            return answer, sessions[0].get_sources(), sessions[0].get_last_chat_history()

        top_k = similarity_top_k or self.settings.rag_top_k
        retriever = MultiPaperRetriever(sessions, similarity_top_k=top_k)

        try:
            chat_engine = CondensePlusContextChatEngine.from_defaults(
                retriever=retriever,
                chat_history=chat_history or [],
                # Every session's postprocessors are built from this same
                # PaperSessionManager's settings (similarity cutoff + optional
                # reranker), so reusing the first session's list applies the
                # same relevance filtering here as a single-paper chat would.
                node_postprocessors=sessions[0]._node_postprocessors,
            )
            response = chat_engine.chat(message)
            sources = _extract_source_nodes(response)
            return str(response), sources, chat_engine.chat_history
        except Exception as e:
            titles = ", ".join(p.title for p in papers)
            logger.error("Error executing multi-paper chat for papers [%s]: %s", titles, e)
            raise QueryExecutionError(f"Failed to chat across papers [{titles}]: {e}") from e
