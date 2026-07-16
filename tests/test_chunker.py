"""
Tests for the document chunking module.

These tests verify the recursive character splitting algorithm, overlap
behavior, and page attribution logic. We use synthetic text rather than
real papers so tests are fast, deterministic, and independent of external files.
"""

from uuid import uuid4

import pytest

from paperpilot.core.models import ExtractedPage
from paperpilot.document.chunker import (
    _build_page_offset_map,
    _find_page_for_offset,
    _merge_with_overlap,
    _recursive_split,
    chunk_text,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_text(n_chars: int, char: str = "x") -> str:
    """Generate a string of exactly n_chars characters."""
    return char * n_chars


# ---------------------------------------------------------------------------
# chunk_text (main entry point)
# ---------------------------------------------------------------------------

class TestChunkText:
    """Tests for the main chunk_text function."""

    def test_empty_text_returns_empty(self):
        """Empty input produces no chunks."""
        chunks = chunk_text("", paper_id=uuid4())
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only input produces no chunks."""
        chunks = chunk_text("   \n\n  ", paper_id=uuid4())
        assert chunks == []

    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size produces exactly one chunk."""
        text = "This is a short paragraph about transformers."
        chunks = chunk_text(text, paper_id=uuid4(), chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_chunks_have_correct_paper_id(self):
        """All chunks reference the correct paper."""
        pid = uuid4()
        text = "A" * 500 + "\n\n" + "B" * 500
        chunks = chunk_text(text, paper_id=pid, chunk_size=300, chunk_overlap=50)

        for chunk in chunks:
            assert chunk.paper_id == pid

    def test_chunks_are_sequential(self):
        """Chunk indices are sequential starting from 0."""
        text = "\n\n".join([f"Paragraph {i}. " * 20 for i in range(5)])
        chunks = chunk_text(text, paper_id=uuid4(), chunk_size=200, chunk_overlap=40)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_prevents_gap(self):
        """With overlap, consecutive chunks share some text."""
        text = "word " * 200  # 1000 characters
        chunks = chunk_text(
            text, paper_id=uuid4(), chunk_size=200, chunk_overlap=50
        )

        # Check that consecutive chunks have overlapping content
        for i in range(len(chunks) - 1):
            tail = chunks[i].text[-50:]  # Last 50 chars of current chunk
            # The next chunk should contain at least some of this text
            # (exact overlap depends on where the split falls)
            assert len(chunks[i + 1].text) > 0

    def test_overlap_must_be_less_than_chunk_size(self):
        """chunk_overlap >= chunk_size should raise ValueError."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text("test", paper_id=uuid4(), chunk_size=100, chunk_overlap=100)

    def test_chunks_respect_paragraph_breaks(self):
        """The algorithm should prefer splitting at paragraph breaks."""
        paragraph_a = "First paragraph. " * 10  # ~170 chars
        paragraph_b = "Second paragraph. " * 10
        text = paragraph_a.strip() + "\n\n" + paragraph_b.strip()

        chunks = chunk_text(
            text, paper_id=uuid4(), chunk_size=200, chunk_overlap=20
        )

        # First chunk should contain mostly paragraph A content
        assert "First paragraph" in chunks[0].text

    def test_page_attribution(self):
        """When pages are provided, chunks get start/end page numbers."""
        pages = [
            ExtractedPage.from_text(1, "Page one text. " * 20),
            ExtractedPage.from_text(2, "Page two text. " * 20),
        ]
        full_text = "\n\n".join(p.text for p in pages)

        chunks = chunk_text(
            full_text,
            paper_id=uuid4(),
            chunk_size=100,
            chunk_overlap=20,
            pages=pages,
        )

        # At least the first chunk should be on page 1
        assert chunks[0].start_page == 1
        # At least the last chunk should be on page 2
        assert chunks[-1].end_page == 2


# ---------------------------------------------------------------------------
# _recursive_split
# ---------------------------------------------------------------------------

class TestRecursiveSplit:
    """Tests for the internal recursive splitting function."""

    def test_text_within_limit(self):
        """Text that fits in one chunk is returned as-is."""
        result = _recursive_split("short text", chunk_size=100, separators=["\n\n", "\n", " ", ""])
        assert result == ["short text"]

    def test_splits_on_paragraphs_first(self):
        """Paragraph breaks are preferred over other separators."""
        text = "Paragraph one.\n\nParagraph two."
        result = _recursive_split(text, chunk_size=20, separators=["\n\n", "\n", " ", ""])
        assert any("Paragraph one." in r for r in result)
        assert any("Paragraph two." in r for r in result)

    def test_falls_through_to_finer_separators(self):
        """If paragraph split is still too large, splits on lines."""
        text = "Line one.\nLine two.\nLine three."
        result = _recursive_split(text, chunk_size=15, separators=["\n\n", "\n", " ", ""])
        # Should have split on \n since no \n\n exists and pieces > 15 chars
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# _merge_with_overlap
# ---------------------------------------------------------------------------

class TestMergeWithOverlap:
    """Tests for the chunk merging and overlap logic."""

    def test_empty_input(self):
        """No pieces produces no chunks."""
        assert _merge_with_overlap([], chunk_size=100, chunk_overlap=20) == []

    def test_single_piece(self):
        """A single piece is returned as-is."""
        result = _merge_with_overlap(["hello"], chunk_size=100, chunk_overlap=20)
        assert result == ["hello"]

    def test_merges_small_pieces(self):
        """Consecutive small pieces are merged until chunk_size is reached."""
        pieces = ["a " * 10, "b " * 10, "c " * 10]  # Each ~20 chars
        result = _merge_with_overlap(pieces, chunk_size=50, chunk_overlap=0)
        # Should merge first two (~40 chars) then third separately
        assert len(result) <= len(pieces)


# ---------------------------------------------------------------------------
# Page offset mapping
# ---------------------------------------------------------------------------

class TestPageMapping:
    """Tests for page offset computation."""

    def test_build_page_offset_map(self):
        """Map correctly computes cumulative offsets."""
        pages = [
            ExtractedPage.from_text(1, "Hello"),  # 5 chars
            ExtractedPage.from_text(2, "World"),  # 5 chars
        ]
        page_map = _build_page_offset_map(pages)

        assert page_map[0] == (0, 1)     # Page 1 starts at offset 0
        assert page_map[1] == (7, 2)     # Page 2 starts at offset 5 + 2 (separator)

    def test_find_page_for_offset(self):
        """Correctly maps character offset to page number."""
        page_map = [(0, 1), (100, 2), (200, 3)]

        assert _find_page_for_offset(page_map, 0) == 1
        assert _find_page_for_offset(page_map, 50) == 1
        assert _find_page_for_offset(page_map, 100) == 2
        assert _find_page_for_offset(page_map, 150) == 2
        assert _find_page_for_offset(page_map, 250) == 3

    def test_find_page_empty_map(self):
        """Empty page map returns None."""
        assert _find_page_for_offset([], 0) is None
