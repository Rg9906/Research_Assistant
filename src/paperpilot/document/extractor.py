"""
PDF text extraction using PyMuPDF (fitz).

This module is responsible for the first step of the document processing
pipeline: taking a PDF file and producing structured, page-by-page text.

How PDFs store text (important context):
    PDFs are NOT plain text documents. Internally, a PDF is a collection of
    drawing instructions: "place glyph 'A' at coordinate (72, 100), then
    place glyph 'B' at coordinate (78, 100)..." There's no inherent concept
    of "words," "lines," or "paragraphs" — the renderer just draws characters
    at specific positions.

    This means text extraction is fundamentally a reconstruction problem.
    The library must:
    1. Identify which glyphs are on each page.
    2. Group nearby glyphs into words (using spatial proximity).
    3. Group words into lines (using vertical alignment).
    4. Order lines into reading sequence (tricky for multi-column layouts).
    5. Handle special characters, ligatures, and encoding issues.

    This is why different PDF extraction libraries produce different results,
    and why some PDFs extract cleanly while others produce garbled text.

Why PyMuPDF?
    - Fast: Written in C, wraps MuPDF (the same engine behind Sumatra PDF).
    - Reliable: Handles most PDF encodings and layouts well.
    - Mature: Actively maintained, extensive documentation.
    - Alternatives: pdfplumber (slower, better tables), PyPDF2 (pure Python,
      slower), pdfminer.six (very configurable, complex API).

    We chose PyMuPDF because research papers are primarily text (not tables),
    speed matters when processing many papers, and the API is straightforward.
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF uses 'fitz' as its import name (after the Fitz imaging library)

from paperpilot.core.models import ExtractedPage

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails.

    Having a domain-specific exception (rather than letting raw PyMuPDF
    errors bubble up) means callers can catch extraction failures without
    knowing which PDF library we use internally. If we swap PyMuPDF for
    another library later, the exception contract doesn't change.
    """


def extract_text_from_pdf(pdf_path: Path | str) -> list[ExtractedPage]:
    """Extract text from a PDF file, returning one ExtractedPage per page.

    This is the main entry point for text extraction. It opens the PDF,
    iterates through each page, extracts text, and returns structured results.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        A list of ExtractedPage objects, one per page, in order.

    Raises:
        PDFExtractionError: If the file doesn't exist, isn't a valid PDF,
                            or extraction fails for any reason.
        FileNotFoundError: If the specified path doesn't exist.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not pdf_path.suffix.lower() == ".pdf":
        raise PDFExtractionError(
            f"Expected a .pdf file, got: {pdf_path.suffix}"
        )

    logger.info("Extracting text from: %s", pdf_path.name)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise PDFExtractionError(
            f"Failed to open PDF '{pdf_path.name}': {e}"
        ) from e

    pages: list[ExtractedPage] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # get_text("text") extracts plain text in reading order.
            # Other options:
            #   "blocks" — returns text grouped by visual blocks
            #   "dict"   — returns full layout information (fonts, sizes, positions)
            #   "html"   — returns HTML representation
            # We use "text" because we want clean, readable text for chunking.
            raw_text = page.get_text("text")

            # Clean up common extraction artifacts
            cleaned_text = _clean_extracted_text(raw_text)

            extracted_page = ExtractedPage.from_text(
                page_number=page_num + 1,  # Convert 0-indexed to 1-indexed
                text=cleaned_text,
            )

            pages.append(extracted_page)

            logger.debug(
                "Page %d: %d characters extracted",
                extracted_page.page_number,
                extracted_page.char_count,
            )
    finally:
        # Always close the document to free resources
        doc.close()

    total_chars = sum(p.char_count for p in pages)
    logger.info(
        "Extraction complete: %d pages, %d total characters",
        len(pages),
        total_chars,
    )

    return pages


def _clean_extracted_text(text: str) -> str:
    """Clean common artifacts from PDF-extracted text.

    PDF extraction often introduces artifacts that degrade downstream quality:
    - Excessive whitespace from layout reconstruction
    - Hyphenation at line breaks (e.g., "trans-\\nformer" → "transformer")
    - Multiple consecutive newlines from column/section breaks

    This function applies conservative cleaning. We intentionally keep it
    simple — aggressive cleaning risks removing meaningful formatting.
    More sophisticated cleaning (e.g., removing headers/footers, fixing
    ligatures) can be added as separate pipeline steps later.

    Args:
        text: Raw extracted text from a PDF page.

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    # Replace common ligatures that some PDFs use
    # (PyMuPDF usually handles these, but some PDFs are stubborn)
    ligature_map = {
        "\ufb01": "fi",  # fi ligature
        "\ufb02": "fl",  # fl ligature
        "\ufb00": "ff",  # ff ligature
        "\ufb03": "ffi",  # ffi ligature
        "\ufb04": "ffl",  # ffl ligature
    }
    for ligature, replacement in ligature_map.items():
        text = text.replace(ligature, replacement)

    # Rejoin hyphenated words that were split across lines
    # Pattern: "word-\n" followed by a lowercase letter → join them
    # We use a simple approach rather than regex for clarity
    lines = text.split("\n")
    rejoined_lines: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if line ends with a hyphen and next line starts with lowercase
        if (
            line.rstrip().endswith("-")
            and i + 1 < len(lines)
            and lines[i + 1].strip()
            and lines[i + 1].strip()[0].islower()
        ):
            # Remove the trailing hyphen and join with next line
            rejoined_lines.append(
                line.rstrip()[:-1] + lines[i + 1].strip()
            )
            i += 2  # Skip the next line since we merged it
        else:
            rejoined_lines.append(line)
            i += 1

    text = "\n".join(rejoined_lines)

    # Collapse runs of 3+ newlines into 2 (preserve paragraph breaks)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def get_full_text(pages: list[ExtractedPage]) -> str:
    """Concatenate all pages into a single text string.

    Pages are joined with double newlines to preserve paragraph separation
    between page boundaries.

    Args:
        pages: List of ExtractedPage objects (typically from extract_text_from_pdf).

    Returns:
        The full document text as a single string.
    """
    return "\n\n".join(page.text for page in pages if page.text)
