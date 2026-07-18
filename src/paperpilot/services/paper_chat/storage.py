"""Storage and directory management for cached paper indexes."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from paperpilot.config import get_settings

logger = logging.getLogger(__name__)


class IndexStorageManager:
    """Manages storage paths and index persistence checks for paper indexes."""

    def __init__(self, base_storage_dir: Path | str | None = None) -> None:
        if base_storage_dir:
            self.base_dir = Path(base_storage_dir)
        else:
            settings = get_settings()
            self.base_dir = settings.data_dir / "indexes"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_paper_index_dir(self, paper_id: UUID | str) -> Path:
        """Return the directory path for storing a paper's index."""
        index_dir = self.base_dir / f"paper_{paper_id}"
        index_dir.mkdir(parents=True, exist_ok=True)
        return index_dir

    def index_exists(self, paper_id: UUID | str) -> bool:
        """Check whether a persisted LlamaIndex index exists for the paper."""
        index_dir = self.base_dir / f"paper_{paper_id}"
        if not index_dir.exists():
            return False
        
        docstore_file = index_dir / "docstore.json"
        index_store_file = index_dir / "index_store.json"
        return docstore_file.exists() or index_store_file.exists()
