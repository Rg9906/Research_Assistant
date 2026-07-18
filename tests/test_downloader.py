"""Unit tests for the PDFDownloader."""

from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from paperpilot.document.downloader import PDFDownloader, UnsafeDownloadURLError, normalize_pdf_url


def test_url_normalization():
    """Should correctly normalize various academic URL patterns."""
    assert (
        normalize_pdf_url("https://arxiv.org/abs/1706.03762v5")
        == "https://arxiv.org/pdf/1706.03762v5.pdf"
    )
    assert (
        normalize_pdf_url("https://arxiv.org/abs/1706.03762")
        == "https://arxiv.org/pdf/1706.03762.pdf"
    )
    assert (
        normalize_pdf_url("https://arxiv.org/pdf/1706.03762")
        == "https://arxiv.org/pdf/1706.03762.pdf"
    )
    assert (
        normalize_pdf_url("https://arxiv.org/pdf/1706.03762.pdf")
        == "https://arxiv.org/pdf/1706.03762.pdf"
    )
    assert normalize_pdf_url("https://example.com/paper.pdf") == "https://example.com/paper.pdf"


def test_download_valid_pdf(tmp_path):
    """Should successfully download and validate a valid PDF."""
    papers_dir = tmp_path / "papers"
    # file:// is disallowed by default (production pdf_url values come from
    # user/API input, so only http/https are trusted); this test explicitly
    # opts in to exercise a local fixture without a network call.
    downloader = PDFDownloader(papers_dir=papers_dir, allowed_schemes=("http", "https", "file"))

    # 1. Create a valid local PDF
    source_pdf = tmp_path / "source.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.insert_text(fitz.Point(10, 10), "Test content")
    doc.save(str(source_pdf))
    doc.close()

    # 2. Download via file:// URL
    file_url = source_pdf.as_uri()
    paper_id = uuid4()

    dest_path = downloader.download_pdf(paper_id, file_url)

    assert dest_path.exists()
    assert dest_path.name == f"{paper_id}.pdf"
    assert dest_path.parent == papers_dir

    # Verify it is valid
    with fitz.open(dest_path) as verify_doc:
        assert verify_doc.page_count == 1


def test_download_invalid_pdf_throws(tmp_path):
    """Should fail download validation and cleanup temporary files if not a PDF."""
    papers_dir = tmp_path / "papers"
    downloader = PDFDownloader(
        papers_dir=papers_dir, max_retries=1, allowed_schemes=("http", "https", "file")
    )

    # Create an invalid text file named as a PDF
    source_txt = tmp_path / "fake.pdf"
    source_txt.write_text("This is not a PDF file content.")

    file_url = source_txt.as_uri()
    paper_id = uuid4()

    with pytest.raises(RuntimeError):
        downloader.download_pdf(paper_id, file_url)

    # Destination should not exist
    dest_path = papers_dir / f"{paper_id}.pdf"
    assert not dest_path.exists()

    # Temp file should be cleaned up
    temp_path = papers_dir / f"tmp_{paper_id}.pdf"
    assert not temp_path.exists()


def test_download_rejects_disallowed_scheme(tmp_path):
    """Should reject file:// (and other non-http(s)) URLs by default.

    pdf_url values come from user-supplied API requests or third-party search
    results, so the default scheme allowlist must exclude `file` to prevent
    local file disclosure.
    """
    papers_dir = tmp_path / "papers"
    downloader = PDFDownloader(papers_dir=papers_dir)

    with pytest.raises(UnsafeDownloadURLError):
        downloader.download_pdf(uuid4(), "file:///etc/passwd")
