"""Unit tests for the PDFDownloader."""

import urllib.error
from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from paperpilot.document.downloader import (
    PDFDownloader,
    PDFUnavailableError,
    UnsafeDownloadURLError,
    normalize_pdf_url,
)


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


class TestPermanentFailures:
    """A dead / paywalled / non-PDF link must fail fast, not burn the retry budget."""

    def test_http_403_fails_immediately_without_retrying(self, tmp_path, monkeypatch):
        downloader = PDFDownloader(papers_dir=tmp_path / "papers", max_retries=3)
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        monkeypatch.setattr("paperpilot.document.downloader.urllib.request.urlopen", fake_urlopen)

        with pytest.raises(PDFUnavailableError, match="subscription or login"):
            downloader.download_pdf(uuid4(), "https://publisher.example/paper")
        assert calls["n"] == 1, "a 403 will never clear, so it must not be retried"

    def test_429_is_still_retried(self, tmp_path, monkeypatch):
        downloader = PDFDownloader(papers_dir=tmp_path / "papers", max_retries=2)
        calls = {"n": 0}
        monkeypatch.setattr("paperpilot.document.downloader.time.sleep", lambda s: None)

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

        monkeypatch.setattr("paperpilot.document.downloader.urllib.request.urlopen", fake_urlopen)

        with pytest.raises(RuntimeError):
            downloader.download_pdf(uuid4(), "https://api.example/paper")
        assert calls["n"] == 2, "429 is transient and should exhaust the retry budget"

    def test_non_pdf_content_is_reported_as_permanent(self, tmp_path):
        """A link that serves HTML (a landing page) is unavailable, not retryable."""
        papers_dir = tmp_path / "papers"
        downloader = PDFDownloader(
            papers_dir=papers_dir, max_retries=3, allowed_schemes=("http", "https", "file")
        )
        html = tmp_path / "landing.pdf"
        html.write_text("<html><body>Please subscribe to read this paper.</body></html>")

        with pytest.raises(PDFUnavailableError, match="valid PDF"):
            downloader.download_pdf(uuid4(), html.as_uri())

    def test_unavailable_error_is_a_runtime_error(self):
        # Existing callers catch RuntimeError; the new type must stay compatible.
        assert issubclass(PDFUnavailableError, RuntimeError)


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
