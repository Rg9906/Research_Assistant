"""Integration tests for multi-paper workspaces in the DocumentPipeline."""

import os
from pathlib import Path
from uuid import UUID, uuid4

import fitz
import pytest

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.pipeline import DocumentPipeline
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore
from paperpilot.workspace.manager import WorkspaceManager


@pytest.fixture
def workspace_setup(tmp_path):
    """Fixture to set up database, index paths, and dummy documents."""
    db_path = tmp_path / "workspace_test.db"
    db_manager = WorkspaceManager(db_path)
    workspace_id = db_manager.create_workspace("Test Workspace")

    # Override Settings directory locations so we write to tmp_path
    settings = get_settings()
    original_index_dir = settings.index_dir
    settings.index_dir = tmp_path / "indexes"
    settings.index_dir.mkdir(parents=True, exist_ok=True)

    # Create two synthetic PDFs
    pdf1_path = tmp_path / "paper1.pdf"
    doc1 = fitz.open()
    page1 = doc1.new_page(width=600, height=800)
    page1.insert_text(
        fitz.Point(50, 50),
        "Attention mechanism relies on key, query, and value vector computations.",
        fontsize=11,
    )
    doc1.save(str(pdf1_path))
    doc1.close()

    pdf2_path = tmp_path / "paper2.pdf"
    doc2 = fitz.open()
    page2 = doc2.new_page(width=600, height=800)
    page2.insert_text(
        fitz.Point(50, 50),
        "Contrastive representation learning pushes positive pairs together and negative pairs apart.",
        fontsize=11,
    )
    doc2.save(str(pdf2_path))
    doc2.close()

    yield db_manager, workspace_id, pdf1_path, pdf2_path

    # Clean up settings overrides
    settings.index_dir = original_index_dir


def test_multi_paper_workspace_indexing_and_retrieval(workspace_setup):
    """Should index two papers in the same workspace and retrieve relevant context across both."""
    db_manager, workspace_id, pdf1_path, pdf2_path = workspace_setup

    engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")
    # Empty index initially
    store = FAISSVectorStore(dimension=engine.embedding_dim)

    # 1. Initialize pipeline with active workspace
    pipeline = DocumentPipeline(
        engine=engine,
        store=store,
        db_manager=db_manager,
        workspace_id=workspace_id,
    )

    # 2. Process first paper
    meta1 = PaperMetadata(title="Transformer Attention", source=PaperSource.MANUAL)
    pipeline.process_pdf(pdf1_path, metadata=meta1, chunk_size=300, chunk_overlap=10)

    # 3. Process second paper
    meta2 = PaperMetadata(title="Contrastive Learning", source=PaperSource.MANUAL)
    pipeline.process_pdf(pdf2_path, metadata=meta2, chunk_size=300, chunk_overlap=10)

    # 4. Assert SQLite metadata counts
    papers = db_manager.get_workspace_papers(workspace_id)
    assert len(papers) == 2
    titles = [p.title for p in papers]
    assert "Transformer Attention" in titles
    assert "Contrastive Learning" in titles

    # 5. Load a fresh pipeline instance and load the workspace
    fresh_store = FAISSVectorStore(dimension=engine.embedding_dim)
    fresh_pipeline = DocumentPipeline(
        engine=engine,
        store=fresh_store,
        db_manager=db_manager,
        workspace_id=workspace_id,
    )

    # Verify that load_workspace was triggered in fresh_pipeline init
    assert len(fresh_pipeline._chunk_registry) > 0

    # 6. Retrieve for query 1 (should match paper 1)
    results1 = fresh_pipeline.retrieve("attention query value vectors", top_k=1)
    assert len(results1) == 1
    assert "key, query, and value" in results1[0].chunk.text
    assert results1[0].chunk.paper_id == meta1.paper_id

    # 7. Retrieve for query 2 (should match paper 2)
    results2 = fresh_pipeline.retrieve("positive pairs negative contrastive", top_k=1)
    assert len(results2) == 1
    assert "positive pairs" in results2[0].chunk.text
    assert results2[0].chunk.paper_id == meta2.paper_id
