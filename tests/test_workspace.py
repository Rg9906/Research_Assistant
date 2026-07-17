"""Unit tests for the WorkspaceManager."""

import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from paperpilot.core.models import ChunkingStrategy, PaperMetadata, PaperSource, TextChunk
from paperpilot.workspace.manager import WorkspaceManager


@pytest.fixture
def temp_db(tmp_path) -> Path:
    """Fixture providing a temporary SQLite database path."""
    return tmp_path / "test_workspace.db"


def test_db_initialization(temp_db):
    """WorkspaceManager should initialize database and create tables successfully."""
    manager = WorkspaceManager(temp_db)
    assert temp_db.exists()

    # Verify tables exist by querying sqlite_master
    with manager._get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "workspaces" in tables
        assert "papers" in tables
        assert "workspace_papers" in tables
        assert "text_chunks" in tables


def test_create_workspace(temp_db):
    """Should create workspace with unique name and return its UUID."""
    manager = WorkspaceManager(temp_db)

    ws_id = manager.create_workspace("Test Workspace")
    assert isinstance(ws_id, UUID)

    # Verify workspace was inserted
    workspaces = manager.list_workspaces()
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Test Workspace"
    assert workspaces[0]["workspace_id"] == ws_id
    assert workspaces[0]["paper_count"] == 0

    # Verify duplicate name raises error
    with pytest.raises(ValueError, match="already exists"):
        manager.create_workspace("Test Workspace")


def test_delete_workspace(temp_db):
    """Deleting a workspace should cascade delete dependencies."""
    manager = WorkspaceManager(temp_db)
    ws_id = manager.create_workspace("Test Workspace")

    paper = PaperMetadata(
        title="Test Paper",
        authors=["Author A"],
        source=PaperSource.MANUAL,
    )
    chunks = [
        TextChunk(
            paper_id=paper.paper_id,
            chunk_index=0,
            text="Chunk text example",
            char_count=18,
        )
    ]

    manager.add_paper_to_workspace(ws_id, paper, chunks)

    # Assert paper and chunks are stored
    assert len(manager.get_workspace_papers(ws_id)) == 1
    assert len(manager.get_chunks_for_workspace(ws_id)) == 1

    # Delete workspace
    manager.delete_workspace(ws_id)
    assert len(manager.list_workspaces()) == 0

    # Cascade deletes should remove workspace mapping, but papers and chunks can remain
    # in the general papers list, or in the workspace_papers table they are deleted.
    with manager._get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM workspace_papers WHERE workspace_id = ?;", (str(ws_id),)
        ).fetchone()
        assert row["count"] == 0


def test_add_and_retrieve_paper(temp_db):
    """Should successfully add paper and its chunks to workspace and retrieve them."""
    manager = WorkspaceManager(temp_db)
    ws_id = manager.create_workspace("ML Papers")

    paper = PaperMetadata(
        title="Attention is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        publication_year=2017,
        citation_count=120000,
        abstract="The dominant sequence transduction models...",
        doi="10.48550/arXiv.1706.03762",
        pdf_url="https://arxiv.org/pdf/1706.03762",
        source=PaperSource.ARXIV,
        venue="NeurIPS",
        keywords=["transformer", "attention"],
    )

    chunks = [
        TextChunk(
            paper_id=paper.paper_id,
            chunk_index=0,
            text="The dominant sequence transduction models...",
            char_count=43,
            start_page=1,
            end_page=1,
            strategy=ChunkingStrategy.RECURSIVE_CHARACTER,
            metadata={"heading": "Abstract"},
        ),
        TextChunk(
            paper_id=paper.paper_id,
            chunk_index=1,
            text="We propose a new simple network architecture, the Transformer...",
            char_count=64,
            start_page=1,
            end_page=1,
            strategy=ChunkingStrategy.RECURSIVE_CHARACTER,
            metadata={"heading": "Introduction"},
        ),
    ]

    manager.add_paper_to_workspace(ws_id, paper, chunks)

    # 1. Retrieve papers
    papers = manager.get_workspace_papers(ws_id)
    assert len(papers) == 1
    retrieved_paper = papers[0]
    assert retrieved_paper.paper_id == paper.paper_id
    assert retrieved_paper.title == paper.title
    assert retrieved_paper.authors == paper.authors
    assert retrieved_paper.publication_year == paper.publication_year
    assert retrieved_paper.citation_count == paper.citation_count
    assert retrieved_paper.source == paper.source

    # 2. Retrieve chunks
    retrieved_chunks = manager.get_chunks_for_workspace(ws_id)
    assert len(retrieved_chunks) == 2
    assert retrieved_chunks[0].chunk_id == chunks[0].chunk_id
    assert retrieved_chunks[0].text == chunks[0].text
    assert retrieved_chunks[0].metadata == chunks[0].metadata
    assert retrieved_chunks[1].chunk_id == chunks[1].chunk_id
