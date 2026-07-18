"""PaperSession domain object and PaperSessionManager for managing paper-centric document intelligence."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any
from uuid import UUID

from paperpilot.core.models import PaperMetadata
from paperpilot.services.paper_chat.storage import IndexStorageManager
from paperpilot.services.paper_chat.ingestion import PaperIngestionService
from paperpilot.services.paper_chat.indexing import PaperIndexingService
from paperpilot.services.paper_chat.query import PaperQueryService

logger = logging.getLogger(__name__)


class PaperSession:
    """Domain object representing an active session for a research paper.

    Owns:
    - paper metadata
    - storage path
    - LlamaIndex index
    - ChatEngine & QueryEngine
    """

    def __init__(
        self,
        metadata: PaperMetadata,
        storage_dir: Path,
        index: Any,
        chat_engine: Any = None,
    ) -> None:
        self.metadata = metadata
        self.paper_id = metadata.paper_id
        self.storage_dir = storage_dir
        self.index = index
        self._chat_engine = chat_engine or PaperQueryService.create_chat_engine(index)

    def chat(self, message: str) -> str:
        """Send a chat message to LlamaIndex ChatEngine and return the response."""
        response = self._chat_engine.chat(message)
        return str(response)

    def query(self, query_str: str) -> str:
        """Execute a single-shot query against the LlamaIndex QueryEngine."""
        query_engine = PaperQueryService.create_query_engine(self.index)
        response = query_engine.query(query_str)
        return str(response)


class PaperSessionManager:
    """Manager for obtaining or building cached PaperSession objects."""

    def __init__(
        self,
        storage_manager: IndexStorageManager | None = None,
        ingestion_service: PaperIngestionService | None = None,
        indexing_service: PaperIndexingService | None = None,
    ) -> None:
        self.storage_manager = storage_manager or IndexStorageManager()
        self.ingestion_service = ingestion_service or PaperIngestionService()
        self.indexing_service = indexing_service or PaperIndexingService()
        self._active_sessions: Dict[str, PaperSession] = {}

    def get_or_create_session(
        self,
        metadata: PaperMetadata,
        pdf_url: str | None = None,
    ) -> PaperSession:
        """Get an existing PaperSession or construct a new one.

        Workflow:
        1. Check if session already in memory cache -> return it.
        2. Check if disk index exists -> load index from storage.
        3. Else -> download PDF, load documents via SimpleDirectoryReader,
           build VectorStoreIndex with SentenceSplitter, and persist to disk.
        """
        paper_id_str = str(metadata.paper_id)
        if paper_id_str in self._active_sessions:
            logger.info("Returning cached in-memory PaperSession for paper %s", paper_id_str)
            return self._active_sessions[paper_id_str]

        storage_dir = self.storage_manager.get_paper_index_dir(metadata.paper_id)

        if self.storage_manager.index_exists(metadata.paper_id):
            logger.info("Index exists on disk. Reusing LlamaIndex for paper %s", paper_id_str)
            index = self.indexing_service.load_index(storage_dir)
        else:
            logger.info("Index does not exist on disk. Building new LlamaIndex for paper %s", paper_id_str)
            documents = self.ingestion_service.download_and_load(metadata, pdf_url=pdf_url)
            index = self.indexing_service.build_and_persist_index(documents, storage_dir)

        session = PaperSession(metadata=metadata, storage_dir=storage_dir, index=index)
        self._active_sessions[paper_id_str] = session
        return session
