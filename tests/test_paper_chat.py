"""Unit tests for LlamaIndex PaperSession and PaperSessionManager."""

import pytest
from uuid import uuid4
from pathlib import Path
from paperpilot.core.models import PaperMetadata
from paperpilot.services.paper_chat.storage import IndexStorageManager
from paperpilot.services.paper_chat.session import PaperSessionManager


def test_index_storage_manager(tmp_path: Path):
    storage_mgr = IndexStorageManager(base_storage_dir=tmp_path)
    paper_id = uuid4()
    
    assert not storage_mgr.index_exists(paper_id)
    index_dir = storage_mgr.get_paper_index_dir(paper_id)
    assert index_dir.exists()


def test_paper_session_manager_initialization(tmp_path: Path):
    storage_mgr = IndexStorageManager(base_storage_dir=tmp_path)
    mgr = PaperSessionManager(storage_manager=storage_mgr)
    assert mgr is not None
