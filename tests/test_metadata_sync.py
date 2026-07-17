"""Unit and integration tests for Metadata Sync in the DocumentPipeline."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.pipeline import DocumentPipeline
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore
from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
from paperpilot.workspace.manager import WorkspaceManager


@pytest.fixture
def sync_setup(tmp_path):
    """Fixture to set up database and pipeline."""
    db_path = tmp_path / "sync_test.db"
    db_manager = WorkspaceManager(db_path)
    workspace_id = db_manager.create_workspace("Sync Workspace")

    engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")
    store = FAISSVectorStore(dimension=engine.embedding_dim)

    pipeline = DocumentPipeline(
        engine=engine,
        store=store,
        db_manager=db_manager,
        workspace_id=workspace_id,
    )

    yield db_manager, workspace_id, pipeline


def test_sync_paper_metadata_via_doi(sync_setup):
    """Should query Semantic Scholar via DOI and update SQLite paper metadata."""
    db_manager, workspace_id, pipeline = sync_setup

    paper_id = uuid4()
    original_paper = PaperMetadata(
        paper_id=paper_id,
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        doi="10.48550/arXiv.1706.03762",
        citation_count=10,  # Outdated count
        venue=None,
    )
    db_manager.add_paper_to_workspace(workspace_id, original_paper, [])

    # Mock providers
    mock_ss = MagicMock(spec=SemanticScholarProvider)
    mock_arxiv = MagicMock(spec=ArxivProvider)

    pipeline.semantic_scholar_provider = mock_ss
    pipeline.arxiv_provider = mock_arxiv

    # Mock response
    refreshed = PaperMetadata(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        doi="10.48550/arXiv.1706.03762",
        citation_count=120000,  # Refreshed count
        venue="NeurIPS 2017",
        keywords=["transformer", "nlp"],
    )
    mock_ss.get_paper_by_doi.return_value = refreshed

    # Act
    synced = pipeline.sync_paper_metadata(paper_id)

    # Assert
    assert synced.paper_id == paper_id
    assert synced.citation_count == 120000
    assert synced.venue == "NeurIPS 2017"
    assert "Noam Shazeer" in synced.authors
    assert "nlp" in synced.keywords

    # Verify DB was updated
    papers_in_db = db_manager.get_workspace_papers(workspace_id)
    assert len(papers_in_db) == 1
    db_paper = papers_in_db[0]
    assert db_paper.citation_count == 120000
    assert db_paper.venue == "NeurIPS 2017"
    assert "nlp" in db_paper.keywords

    mock_ss.get_paper_by_doi.assert_called_once_with("10.48550/arXiv.1706.03762")


def test_sync_paper_metadata_via_arxiv_id(sync_setup):
    """Should query ArXiv via parsed arXiv ID when DOI is missing."""
    db_manager, workspace_id, pipeline = sync_setup

    paper_id = uuid4()
    original_paper = PaperMetadata(
        paper_id=paper_id,
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        pdf_url="https://arxiv.org/pdf/1706.03762.pdf",  # ArXiv ID is extractable from URL
        citation_count=0,
    )
    db_manager.add_paper_to_workspace(workspace_id, original_paper, [])

    # Mock providers
    mock_ss = MagicMock(spec=SemanticScholarProvider)
    mock_arxiv = MagicMock(spec=ArxivProvider)

    pipeline.semantic_scholar_provider = mock_ss
    pipeline.arxiv_provider = mock_arxiv

    mock_ss.get_paper_by_doi.return_value = None
    mock_ss.get_paper_by_arxiv.return_value = None

    # Mock ArXiv response
    refreshed = PaperMetadata(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
        abstract="We propose a new simple network architecture, the Transformer...",
        venue="arXiv Preprint",
        keywords=["arxiv", "1706.03762"],
    )
    mock_arxiv.get_paper_by_id.return_value = refreshed

    # Act
    synced = pipeline.sync_paper_metadata(paper_id)

    # Assert
    assert synced.paper_id == paper_id
    assert synced.abstract.startswith("We propose a new simple network")

    # Verify DB was updated
    papers_in_db = db_manager.get_workspace_papers(workspace_id)
    assert len(papers_in_db) == 1
    assert papers_in_db[0].abstract.startswith("We propose a new simple network")

    mock_arxiv.get_paper_by_id.assert_called_once_with("1706.03762")
