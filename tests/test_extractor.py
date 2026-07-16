"""
Tests for the PDF text extraction module.

Note: PDF extraction tests require a real PDF file. These tests use a small
synthetic PDF created in-memory via PyMuPDF. This avoids depending on external
files while still testing real PDF extraction behavior.
"""

from pathlib import Path

import fitz  # PyMuPDF
import pytest

from paperpilot.document.extractor import (
    PDFExtractionError,
    _clean_extracted_text,
    extract_text_from_pdf,
    get_full_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a small synthetic PDF with known content.

    We use PyMuPDF's document creation API to build a PDF in-memory,
    write it to a temp file, and return the path. This way tests don't
    depend on any external PDF file.
    """
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()  # Create a new empty PDF

    # Page 1
    page1 = doc.new_page(width=612, height=792)  # US Letter size
    page1.insert_text(
        fitz.Point(72, 72),
        "Introduction\n\nThis paper explores the transformer architecture.",
        fontsize=11,
    )

    # Page 2
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text(
        fitz.Point(72, 72),
        "Methods\n\nWe propose a novel attention mechanism.",
        fontsize=11,
    )

    # Page 3 (empty — tests should handle gracefully)
    doc.new_page(width=612, height=792)

    doc.save(str(pdf_path))
    doc.close()

    return pdf_path


@pytest.fixture
def non_pdf_file(tmp_path: Path) -> Path:
    """Create a non-PDF file for error testing."""
    file_path = tmp_path / "document.txt"
    file_path.write_text("This is not a PDF")
    return file_path


# ---------------------------------------------------------------------------
# extract_text_from_pdf
# ---------------------------------------------------------------------------

class TestExtractTextFromPdf:
    """Tests for the main extraction function."""

    def test_extracts_correct_number_of_pages(self, sample_pdf: Path):
        """Should return one ExtractedPage per page in the PDF."""
        pages = extract_text_from_pdf(sample_pdf)
        assert len(pages) == 3  # We created 3 pages

    def test_page_numbers_are_1_indexed(self, sample_pdf: Path):
        """Page numbers should start at 1, not 0."""
        pages = extract_text_from_pdf(sample_pdf)
        page_numbers = [p.page_number for p in pages]
        assert page_numbers == [1, 2, 3]

    def test_extracts_known_content(self, sample_pdf: Path):
        """Should find the text we inserted into the PDF."""
        pages = extract_text_from_pdf(sample_pdf)
        assert "transformer" in pages[0].text.lower()
        assert "attention" in pages[1].text.lower()

    def test_char_count_is_accurate(self, sample_pdf: Path):
        """char_count should match the actual length of the text."""
        pages = extract_text_from_pdf(sample_pdf)
        for page in pages:
            assert page.char_count == len(page.text)

    def test_empty_page_has_zero_or_minimal_chars(self, sample_pdf: Path):
        """An empty page should have 0 (or very few) characters."""
        pages = extract_text_from_pdf(sample_pdf)
        # Page 3 was created empty
        assert pages[2].char_count == 0 or pages[2].text.strip() == ""

    def test_file_not_found_raises_error(self):
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf(Path("/nonexistent/paper.pdf"))

    def test_non_pdf_raises_error(self, non_pdf_file: Path):
        """Should raise PDFExtractionError for non-PDF files."""
        with pytest.raises(PDFExtractionError, match="Expected a .pdf"):
            extract_text_from_pdf(non_pdf_file)

    def test_accepts_string_path(self, sample_pdf: Path):
        """Should accept both Path objects and string paths."""
        pages = extract_text_from_pdf(str(sample_pdf))
        assert len(pages) > 0


# ---------------------------------------------------------------------------
# _clean_extracted_text
# ---------------------------------------------------------------------------

class TestCleanExtractedText:
    """Tests for the text cleaning function."""

    def test_empty_string(self):
        """Empty input returns empty output."""
        assert _clean_extracted_text("") == ""

    def test_ligature_replacement(self):
        """Common ligatures should be replaced with ASCII equivalents."""
        text = "The \ufb01rst \ufb02oor was \ufb00ective."
        cleaned = _clean_extracted_text(text)
        assert "first" in cleaned
        assert "floor" in cleaned
        assert "ffective" in cleaned

    def test_hyphenation_rejoining(self):
        """Words hyphenated across lines should be rejoined."""
        text = "The trans-\nformer architecture is powerful."
        cleaned = _clean_extracted_text(text)
        assert "transformer" in cleaned

    def test_compound_word_at_line_break(self):
        """Compound words like 'self-attention' at line breaks are tricky.

        When a compound word like 'self-' lands at a line break, our greedy
        merge may or may not rejoin it depending on prior merges. This is an
        inherent limitation of heuristic hyphenation — perfect disambiguation
        requires a dictionary. We accept this trade-off for Milestone 1.
        """
        text = "Uses self-\nattention mechanisms."
        cleaned = _clean_extracted_text(text)
        # The cleaner will rejoin this (lowercase 'a' after hyphen),
        # producing "selfattention" — imperfect but consistent behavior.
        assert "selfattention" in cleaned or "self-attention" in cleaned

    def test_preserves_intentional_hyphens(self):
        """Hyphens NOT at line breaks should be preserved."""
        text = "state-of-the-art results"
        cleaned = _clean_extracted_text(text)
        assert "state-of-the-art" in cleaned

    def test_collapses_excessive_newlines(self):
        """Runs of 3+ newlines should be collapsed to 2."""
        text = "Section A\n\n\n\n\nSection B"
        cleaned = _clean_extracted_text(text)
        assert "\n\n\n" not in cleaned
        assert "Section A" in cleaned
        assert "Section B" in cleaned

    def test_strips_whitespace(self):
        """Leading and trailing whitespace should be removed."""
        text = "   \n  Hello world   \n  "
        cleaned = _clean_extracted_text(text)
        assert cleaned == "Hello world"


# ---------------------------------------------------------------------------
# get_full_text
# ---------------------------------------------------------------------------

class TestGetFullText:
    """Tests for the page concatenation function."""

    def test_concatenation(self):
        """Pages are joined with double newlines."""
        from paperpilot.core.models import ExtractedPage

        pages = [
            ExtractedPage.from_text(1, "Page one"),
            ExtractedPage.from_text(2, "Page two"),
        ]
        full = get_full_text(pages)
        assert full == "Page one\n\nPage two"

    def test_empty_pages_skipped(self):
        """Pages with empty text are excluded from concatenation."""
        from paperpilot.core.models import ExtractedPage

        pages = [
            ExtractedPage.from_text(1, "Page one"),
            ExtractedPage.from_text(2, ""),
            ExtractedPage.from_text(3, "Page three"),
        ]
        full = get_full_text(pages)
        assert full == "Page one\n\nPage three"

    def test_empty_list(self):
        """No pages returns empty string."""
        assert get_full_text([]) == ""
