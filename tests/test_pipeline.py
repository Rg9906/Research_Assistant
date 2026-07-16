"""
End-to-end tests for the document processing and retrieval pipeline.

These tests verify the full flow: PDF → Extract → Chunk → Embed → Store → Retrieve.
They use a synthetic PDF and real embedding model to test the entire system
as an integrated unit.
"""

from pathlib import Path

import fitz  # PyMuPDF
import pytest

from paperpilot.core.models import PaperMetadata
from paperpilot.pipeline import DocumentPipeline
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine() -> EmbeddingEngine:
    """Load the embedding model once for all pipeline tests."""
    return EmbeddingEngine(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a multi-topic synthetic PDF for retrieval testing.

    The PDF contains distinct paragraphs on different topics so we can
    verify that retrieval returns the correct chunks for each query.
    """
    pdf_path = tmp_path / "test_paper.pdf"
    doc = fitz.open()

    page = doc.new_page(width=612, height=792)
    text = (
        "Introduction to Transformers\n\n"
        "The transformer architecture was introduced in the paper "
        "Attention Is All You Need by Vaswani et al. in 2017. "
        "It replaced recurrent neural networks with a self-attention "
        "mechanism that processes all positions in parallel. "
        "This breakthrough enabled much faster training and better "
        "performance on sequence-to-sequence tasks.\n\n"
        "Convolutional Neural Networks\n\n"
        "Convolutional neural networks (CNNs) are primarily used for "
        "image recognition and computer vision tasks. They use "
        "convolutional filters to detect spatial patterns like edges, "
        "textures, and shapes. Popular CNN architectures include "
        "ResNet, VGG, and Inception.\n\n"
        "Reinforcement Learning\n\n"
        "Reinforcement learning is a paradigm where an agent learns "
        "to make decisions by interacting with an environment. "
        "The agent receives rewards or penalties for its actions and "
        "learns a policy that maximizes cumulative reward. "
        "Key algorithms include Q-learning, policy gradient methods, "
        "and actor-critic approaches."
    )
    page.insert_text(fitz.Point(50, 50), text, fontsize=11)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def pipeline(engine: EmbeddingEngine) -> DocumentPipeline:
    """Create a fresh pipeline with a new empty vector store."""
    store = FAISSVectorStore(dimension=engine.embedding_dim)
    return DocumentPipeline(engine, store)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocumentPipeline:
    """Tests for the full document processing pipeline."""

    def test_process_pdf_returns_document(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Processing a PDF should return a complete ProcessedDocument."""
        doc = pipeline.process_pdf(sample_pdf)

        assert doc.metadata.title == "test_paper"  # Derived from filename
        assert doc.total_pages >= 1
        assert doc.total_chars > 0
        assert len(doc.pages) >= 1
        assert len(doc.chunks) > 0

    def test_process_pdf_with_metadata(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Custom metadata should be preserved through processing."""
        metadata = PaperMetadata(
            title="Test Paper on ML Topics",
            authors=["Test Author"],
        )
        doc = pipeline.process_pdf(sample_pdf, metadata=metadata)

        assert doc.metadata.title == "Test Paper on ML Topics"
        assert doc.metadata.authors == ["Test Author"]

    def test_chunks_are_indexed(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """After processing, all chunks should be in the vector store."""
        doc = pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        assert pipeline.store.count == len(doc.chunks)

    def test_retrieve_relevant_results(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Querying about transformers should return transformer-related chunks."""
        pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        results = pipeline.retrieve("What is the transformer architecture?", top_k=3)

        assert len(results) > 0
        assert results[0].rank == 1

        # The top result should contain transformer-related content
        top_text = results[0].chunk.text.lower()
        assert any(
            keyword in top_text
            for keyword in ["transformer", "attention", "vaswani"]
        ), f"Expected transformer content, got: {top_text[:100]}"

    def test_retrieve_different_topics(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Different queries should retrieve different chunks."""
        pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        # Query about CNNs
        cnn_results = pipeline.retrieve("convolutional neural networks for images", top_k=1)
        # Query about RL
        rl_results = pipeline.retrieve("reinforcement learning reward policy", top_k=1)

        # Top results should be different chunks
        assert cnn_results[0].chunk.chunk_id != rl_results[0].chunk.chunk_id

        # CNN result should mention CNN-related content
        assert any(
            kw in cnn_results[0].chunk.text.lower()
            for kw in ["convolutional", "cnn", "image"]
        )

        # RL result should mention RL-related content
        assert any(
            kw in rl_results[0].chunk.text.lower()
            for kw in ["reinforcement", "reward", "agent", "policy"]
        )

    def test_results_ordered_by_score(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Results should be ordered by score (ascending L2 distance)."""
        pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        results = pipeline.retrieve("transformer self-attention", top_k=5)

        scores = [r.score for r in results]
        assert scores == sorted(scores), "Results should be sorted by ascending distance"

    def test_results_have_sequential_ranks(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """Results should have ranks 1, 2, 3, ..."""
        pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        results = pipeline.retrieve("neural networks", top_k=3)

        ranks = [r.rank for r in results]
        assert ranks == [1, 2, 3]

    def test_irrelevant_query_has_higher_distances(self, pipeline: DocumentPipeline, sample_pdf: Path):
        """An irrelevant query should produce higher distances than a relevant one."""
        pipeline.process_pdf(sample_pdf, chunk_size=200, chunk_overlap=30)

        relevant = pipeline.retrieve("transformer attention mechanism", top_k=1)
        irrelevant = pipeline.retrieve("cooking pasta recipes Italian food", top_k=1)

        # Irrelevant query should have a higher distance (less similar)
        assert irrelevant[0].score > relevant[0].score, (
            f"Irrelevant score ({irrelevant[0].score:.4f}) should be higher "
            f"than relevant score ({relevant[0].score:.4f})"
        )
