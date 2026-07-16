"""
Tests for core data models.

These tests verify that Pydantic models enforce their contracts correctly:
type validation, default values, constraints, and serialization.
"""

from uuid import UUID

import pytest

from paperpilot.core.models import (
    ChunkingStrategy,
    ExtractedPage,
    PaperMetadata,
    PaperSource,
    ProcessedDocument,
    TextChunk,
)


# ---------------------------------------------------------------------------
# PaperMetadata
# ---------------------------------------------------------------------------

class TestPaperMetadata:
    """Tests for the PaperMetadata model."""

    def test_minimal_creation(self):
        """A paper only requires a title — everything else has defaults."""
        paper = PaperMetadata(title="Attention Is All You Need")

        assert paper.title == "Attention Is All You Need"
        assert isinstance(paper.paper_id, UUID)
        assert paper.authors == []
        assert paper.source == PaperSource.MANUAL
        assert paper.keywords == []
        assert paper.publication_year is None
        assert paper.citation_count is None

    def test_full_creation(self):
        """All fields can be populated."""
        paper = PaperMetadata(
            title="Attention Is All You Need",
            authors=["Vaswani", "Shazeer", "Parmar"],
            publication_year=2017,
            citation_count=100000,
            abstract="The dominant sequence transduction models...",
            doi="10.48550/arXiv.1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
            source=PaperSource.ARXIV,
            venue="NeurIPS 2017",
            keywords=["transformer", "attention", "sequence-to-sequence"],
        )

        assert paper.publication_year == 2017
        assert len(paper.authors) == 3
        assert paper.source == PaperSource.ARXIV

    def test_unique_ids(self):
        """Each paper gets a unique ID by default."""
        p1 = PaperMetadata(title="Paper A")
        p2 = PaperMetadata(title="Paper B")
        assert p1.paper_id != p2.paper_id

    def test_serialization_roundtrip(self):
        """Models can be serialized to JSON and back without data loss."""
        paper = PaperMetadata(
            title="Test Paper",
            authors=["Author A"],
            publication_year=2024,
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        json_str = paper.model_dump_json()
        restored = PaperMetadata.model_validate_json(json_str)

        assert restored.title == paper.title
        assert restored.paper_id == paper.paper_id
        assert restored.source == PaperSource.SEMANTIC_SCHOLAR


# ---------------------------------------------------------------------------
# ExtractedPage
# ---------------------------------------------------------------------------

class TestExtractedPage:
    """Tests for the ExtractedPage model."""

    def test_from_text_factory(self):
        """The from_text factory auto-computes char_count."""
        page = ExtractedPage.from_text(
            page_number=1, text="Hello, world!"
        )
        assert page.page_number == 1
        assert page.text == "Hello, world!"
        assert page.char_count == 13

    def test_page_number_must_be_positive(self):
        """Page numbers must be >= 1."""
        with pytest.raises(ValueError):
            ExtractedPage(page_number=0, text="test", char_count=4)

    def test_immutability(self):
        """ExtractedPages are frozen (immutable)."""
        page = ExtractedPage.from_text(page_number=1, text="test")
        with pytest.raises(Exception):
            page.text = "modified"  # type: ignore


# ---------------------------------------------------------------------------
# TextChunk
# ---------------------------------------------------------------------------

class TestTextChunk:
    """Tests for the TextChunk model."""

    def test_creation(self):
        """Chunks require a paper_id, index, and text."""
        paper = PaperMetadata(title="Test")
        chunk = TextChunk(
            paper_id=paper.paper_id,
            chunk_index=0,
            text="Some text content",
            char_count=17,
        )

        assert chunk.paper_id == paper.paper_id
        assert chunk.chunk_index == 0
        assert chunk.strategy == ChunkingStrategy.RECURSIVE_CHARACTER

    def test_chunk_index_non_negative(self):
        """Chunk index must be >= 0."""
        paper = PaperMetadata(title="Test")
        with pytest.raises(ValueError):
            TextChunk(
                paper_id=paper.paper_id,
                chunk_index=-1,
                text="test",
                char_count=4,
            )

    def test_metadata_dict(self):
        """Chunks can carry arbitrary string metadata."""
        paper = PaperMetadata(title="Test")
        chunk = TextChunk(
            paper_id=paper.paper_id,
            chunk_index=0,
            text="Introduction section",
            char_count=20,
            metadata={"section": "Introduction"},
        )
        assert chunk.metadata["section"] == "Introduction"


# ---------------------------------------------------------------------------
# ProcessedDocument
# ---------------------------------------------------------------------------

class TestProcessedDocument:
    """Tests for the ProcessedDocument model."""

    def test_creation_with_metadata_only(self):
        """A ProcessedDocument can be created with just metadata."""
        paper = PaperMetadata(title="Test Paper")
        doc = ProcessedDocument(metadata=paper)

        assert doc.metadata.title == "Test Paper"
        assert doc.full_text == ""
        assert doc.pages == []
        assert doc.chunks == []
        assert doc.total_pages == 0

    def test_full_document(self):
        """A fully populated ProcessedDocument."""
        paper = PaperMetadata(title="Test Paper")
        pages = [
            ExtractedPage.from_text(1, "Page one content"),
            ExtractedPage.from_text(2, "Page two content"),
        ]
        chunks = [
            TextChunk(
                paper_id=paper.paper_id,
                chunk_index=0,
                text="Page one content",
                char_count=16,
            ),
        ]

        doc = ProcessedDocument(
            metadata=paper,
            full_text="Page one content\n\nPage two content",
            pages=pages,
            chunks=chunks,
            total_pages=2,
            total_chars=32,
        )

        assert doc.total_pages == 2
        assert len(doc.pages) == 2
        assert len(doc.chunks) == 1
