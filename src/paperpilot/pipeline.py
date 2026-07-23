"""Document Pipeline Facade.

Refactored to delegate document intelligence, chunking, embedding, indexing,
and grounded QA directly to LlamaIndex via PaperSessionManager.
"""

import logging
import re
from typing import Any
from uuid import UUID, uuid4

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata, RetrievalResult, TextChunk, ChunkingStrategy
from paperpilot.document.downloader import PDFDownloader
from paperpilot.services.paper_chat import PaperSessionManager, PaperSession
from paperpilot.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)


class DocumentPipeline:
    """Facade for paper downloading, metadata syncing, and LlamaIndex session management.

    LlamaIndex owns the entire document intelligence pipeline:
    - SimpleDirectoryReader for PDF parsing
    - SentenceSplitter for transformations
    - HuggingFace/OpenAI for embeddings & indexing
    - Disk persistence & index caching
    """

    def __init__(
        self,
        engine: Any = None,
        store: Any = None,
        tutor: Any = None,
        db_manager: WorkspaceManager | None = None,
        workspace_id: UUID | None = None,
        session_manager: PaperSessionManager | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.workspace_id = workspace_id
        self.session_manager = session_manager or PaperSessionManager()

        settings = get_settings()
        self.downloader = PDFDownloader(papers_dir=settings.papers_dir)

        from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
        self.arxiv_provider = ArxivProvider()
        self.semantic_scholar_provider = SemanticScholarProvider()

    def get_session(self, metadata: PaperMetadata, pdf_url: str | None = None) -> PaperSession:
        """Obtain a LlamaIndex PaperSession for the given paper."""
        return self.session_manager.get_or_create_session(metadata=metadata, pdf_url=pdf_url)

    def download_and_process_pdf(
        self,
        paper_id: UUID,
        pdf_url: str,
        metadata: PaperMetadata | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> PaperSession:
        """Download PDF and process using LlamaIndex IngestionPipeline."""
        logger.info("Processing PDF via LlamaIndex for paper %s from %s", paper_id, pdf_url)
        if metadata is None:
            metadata = PaperMetadata(paper_id=paper_id, title=f"Paper_{paper_id}", pdf_url=pdf_url)
        else:
            metadata.paper_id = paper_id
            if pdf_url:
                metadata.pdf_url = pdf_url

        session = self.session_manager.get_or_create_session(metadata=metadata, pdf_url=pdf_url)

        if self.workspace_id and self.db_manager:
            self.db_manager.add_paper_to_workspace(self.workspace_id, metadata, chunks=[])

        return session

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        """Backward compatibility for retrieve() in LangGraph agent workflows.

        Performs pure similarity retrieval against the LlamaIndex index (no LLM
        synthesis call) and maps source nodes back to TextChunks.
        """
        if not self.workspace_id or not self.db_manager:
            raise ValueError("WorkspaceManager and workspace_id required to retrieve context.")

        papers = self.db_manager.get_workspace_papers(self.workspace_id)
        if not papers:
            return []

        target_paper = papers[0]
        session = self.get_session(metadata=target_paper, pdf_url=target_paper.pdf_url)

        # Use a retriever (not a query engine) so this stays a pure similarity
        # lookup — as_query_engine().query() would fire a full LLM synthesis
        # call just to fetch chunks.
        retriever = session.index.as_retriever(similarity_top_k=top_k or 5)
        nodes_with_scores = retriever.retrieve(query)

        results = []
        for rank, node_with_score in enumerate(nodes_with_scores, start=1):
            raw_meta = node_with_score.node.metadata or {}
            page_num = raw_meta.get("page_label") or raw_meta.get("page_number") or 1
            try:
                page_num = int(page_num)
            except (TypeError, ValueError):
                page_num = 1

            # TextChunk.metadata is typed dict[str, str]; LlamaIndex node metadata
            # can contain ints/None (e.g. publication_year), so coerce every value.
            meta = {str(k): str(v) for k, v in raw_meta.items() if v is not None}

            chunk = TextChunk(
                chunk_id=uuid4(),
                paper_id=target_paper.paper_id,
                chunk_index=rank,
                text=node_with_score.node.get_content(),
                char_count=len(node_with_score.node.get_content()),
                start_page=page_num,
                end_page=page_num,
                strategy=ChunkingStrategy.RECURSIVE_CHARACTER,
                metadata=meta,
            )
            results.append(RetrievalResult(
                chunk=chunk,
                score=float(node_with_score.score or 0.0),
                rank=rank,
            ))
        return results

    def answer_question(self, query: str, paper_metadata: PaperMetadata | None = None) -> str:
        """Answer a user question grounded in paper context using LlamaIndex ChatEngine."""
        if not self.workspace_id or not self.db_manager:
            raise ValueError("WorkspaceManager and workspace_id required to answer questions.")

        papers = self.db_manager.get_workspace_papers(self.workspace_id)
        if not papers:
            raise ValueError("No papers found in current workspace.")

        target_paper = paper_metadata or papers[0]
        session = self.get_session(metadata=target_paper, pdf_url=target_paper.pdf_url)
        return session.chat(query)

    def sync_paper_metadata(self, paper_id: UUID) -> PaperMetadata:
        """Sync and update paper metadata from external providers (arXiv/Semantic Scholar)."""
        if not self.db_manager:
            raise ValueError("WorkspaceManager must be configured to sync metadata.")

        papers = self.db_manager.get_workspace_papers(self.workspace_id) if self.workspace_id else []
        current_paper = next((p for p in papers if p.paper_id == paper_id), None)
        if not current_paper:
            current_paper = self.db_manager.get_paper_by_id(paper_id)
            if not current_paper:
                raise ValueError(f"Paper with ID {paper_id} not found in database.")

        logger.info("Syncing metadata for paper: '%s'", current_paper.title)

        arxiv_id = None
        if current_paper.keywords:
            for kw in current_paper.keywords:
                if kw != "arxiv" and kw != "semanticscholar" and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", kw):
                    arxiv_id = kw.split("v")[0]
                    break
        if not arxiv_id and current_paper.pdf_url and "arxiv.org" in current_paper.pdf_url:
            match = re.search(r"/pdf/(\d{4}\.\d{4,5})", current_paper.pdf_url)
            if match:
                arxiv_id = match.group(1)
            else:
                match = re.search(r"/abs/(\d{4}\.\d{4,5})", current_paper.pdf_url)
                if match:
                    arxiv_id = match.group(1)

        refreshed_meta = None
        if current_paper.doi:
            refreshed_meta = self.semantic_scholar_provider.get_paper_by_doi(current_paper.doi)
        if not refreshed_meta and arxiv_id:
            refreshed_meta = self.semantic_scholar_provider.get_paper_by_arxiv(arxiv_id)
        if not refreshed_meta and arxiv_id:
            refreshed_meta = self.arxiv_provider.get_paper_by_id(arxiv_id)

        if not refreshed_meta:
            return current_paper

        current_paper.title = refreshed_meta.title or current_paper.title
        current_paper.authors = refreshed_meta.authors or current_paper.authors
        current_paper.publication_year = refreshed_meta.publication_year or current_paper.publication_year
        current_paper.citation_count = refreshed_meta.citation_count or current_paper.citation_count
        current_paper.abstract = refreshed_meta.abstract or current_paper.abstract
        current_paper.doi = refreshed_meta.doi or current_paper.doi
        current_paper.pdf_url = refreshed_meta.pdf_url or current_paper.pdf_url
        current_paper.venue = refreshed_meta.venue or current_paper.venue

        merged_kws = list(set(current_paper.keywords + refreshed_meta.keywords))
        current_paper.keywords = merged_kws

        self.db_manager.update_paper_metadata(current_paper)
        return current_paper
