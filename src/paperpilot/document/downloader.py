"""Document Downloader for downloading and validating PDFs from academic URLs."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import fitz

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_SCHEMES = ("http", "https")
DEFAULT_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — generous for a research paper PDF

# 4xx codes that a retry might actually clear, so they are NOT treated as
# permanent: 408 Request Timeout and 429 Too Many Requests are transient by
# definition. Every other 4xx (403 paywall, 404 gone, 401 auth) will return the
# same result no matter how many times we ask.
_RETRYABLE_HTTP_4XX = {408, 429}


def normalize_pdf_url(url: str) -> str:
    """Normalize academic URLs to point directly to the PDF file.

    e.g., https://arxiv.org/abs/1706.03762v5 -> https://arxiv.org/pdf/1706.03762.pdf
    """
    url = url.strip()
    if "arxiv.org/abs/" in url:
        url = url.replace("arxiv.org/abs/", "arxiv.org/pdf/")
        if not url.endswith(".pdf"):
            url += ".pdf"
    elif "arxiv.org/pdf/" in url and not url.endswith(".pdf"):
        url += ".pdf"
    return url


class UnsafeDownloadURLError(ValueError):
    """Raised when a PDF URL uses a scheme that is not in the downloader's allowlist."""


class PDFUnavailableError(RuntimeError):
    """The PDF cannot be fetched and retrying will not help.

    Distinct from a transient network failure: this means the link is a paywall,
    a dead URL, or a page that serves HTML instead of a PDF — common for the
    `openAccessPdf` links Semantic Scholar returns for closed-access papers.
    Carries a human-readable reason suitable for showing to the user, since a
    RuntimeError subclass so existing `except RuntimeError` callers still catch it.
    """


class PDFDownloader:
    """Handles downloading PDF files from external URLs, verifying validity, and retry logic."""

    def __init__(
        self,
        papers_dir: Path | str,
        timeout: float = 15.0,
        max_retries: int = 3,
        allowed_schemes: tuple[str, ...] = DEFAULT_ALLOWED_SCHEMES,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> None:
        """Initialize the downloader.

        Args:
            papers_dir: Directory where PDFs will be stored.
            timeout: Socket timeout for downloads in seconds.
            max_retries: Maximum download retry attempts.
            allowed_schemes: URL schemes this downloader is permitted to fetch.
                Defaults to http/https only. `pdf_url` values ultimately come
                from user-supplied API requests or third-party search results,
                so allowing arbitrary schemes (e.g. `file://`) would let a
                caller read local files off disk. Tests that need to exercise
                local fixtures should pass an explicit allowlist including
                "file".
            max_download_bytes: Hard cap on response size, enforced both via
                the Content-Length header (when present) and while streaming,
                to avoid loading an unbounded response fully into memory.
        """
        self.papers_dir = Path(papers_dir)
        self.timeout = timeout
        self.max_retries = max_retries
        self.allowed_schemes = allowed_schemes
        self.max_download_bytes = max_download_bytes
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self.papers_dir.mkdir(parents=True, exist_ok=True)

    def download_pdf(self, paper_id: UUID, pdf_url: str) -> Path:
        """Download a PDF from the given URL and store it locally.

        Implements URL normalization, validation of the PDF header, and verification via fitz.

        Args:
            paper_id: UUID of the target paper.
            pdf_url: Remote URL of the paper's PDF.

        Returns:
            Path to the downloaded local PDF file.
        """
        normalized_url = normalize_pdf_url(pdf_url)

        scheme = urlparse(normalized_url).scheme.lower()
        if scheme not in self.allowed_schemes:
            raise UnsafeDownloadURLError(
                f"URL scheme '{scheme}' is not permitted (allowed: {self.allowed_schemes})."
            )

        dest_path = self.papers_dir / f"{paper_id}.pdf"
        temp_path = self.papers_dir / f"tmp_{paper_id}.pdf"

        # Check if already exists and is a valid PDF
        if dest_path.exists():
            try:
                with fitz.open(dest_path) as doc:
                    if doc.page_count > 0:
                        logger.info("PDF already exists and is valid: %s", dest_path)
                        return dest_path
            except Exception:
                logger.warning("Existing PDF corrupted. Re-downloading: %s", dest_path)
                dest_path.unlink(missing_ok=True)

        logger.info("Downloading PDF from %s to %s", normalized_url, dest_path)

        req = urllib.request.Request(normalized_url, headers=self.headers)
        attempt = 0
        backoff = 1.0

        while attempt < self.max_retries:
            attempt += 1
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > self.max_download_bytes:
                        raise ValueError(
                            f"Response Content-Length ({content_length} bytes) exceeds "
                            f"max_download_bytes ({self.max_download_bytes})."
                        )

                    # Stream to a temporary file in chunks, enforcing a hard byte
                    # cap even when Content-Length is absent or understated —
                    # otherwise a single response.read() call would buffer an
                    # unbounded body fully into memory.
                    written = 0
                    chunk_size = 1024 * 1024
                    with open(temp_path, "wb") as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > self.max_download_bytes:
                                raise ValueError(
                                    f"Download exceeded max_download_bytes ({self.max_download_bytes})."
                                )
                            f.write(chunk)

                # Validate PDF structure
                self._validate_pdf(temp_path)

                # Rename to final destination
                temp_path.rename(dest_path)
                logger.info("Successfully downloaded and validated PDF: %s", dest_path)
                return dest_path

            except Exception as e:
                # Clean up temp file on failure
                temp_path.unlink(missing_ok=True)

                # A permanent failure will produce the identical result on every
                # retry, so stop immediately rather than burning the retry budget
                # (and the user's time) re-fetching a paywall or a landing page.
                permanent = self._permanent_reason(e)
                if permanent is not None:
                    logger.warning("PDF unavailable at %s: %s", normalized_url, permanent)
                    raise PDFUnavailableError(permanent) from e

                logger.warning(
                    "Download attempt %d failed for URL %s: %s", attempt, normalized_url, e
                )

                if attempt >= self.max_retries:
                    logger.error("All download attempts failed for URL: %s", normalized_url)
                    raise RuntimeError(
                        f"Could not download the PDF after {self.max_retries} attempts "
                        f"(network error: {e})."
                    ) from e

                # Backoff sleep
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError("Unexpected end of download loop.")

    @staticmethod
    def _permanent_reason(error: Exception) -> str | None:
        """Return a user-facing reason if `error` means retrying is pointless, else None.

        Two permanent cases dominate for third-party `openAccessPdf` links:
        an HTTP 4xx (the file is gone, forbidden, or behind auth), and a
        successful fetch of something that is not a PDF (a publisher landing
        page served as HTML). Both are captured here so the caller can show a
        clear message instead of a raw stack trace.
        """
        if isinstance(error, urllib.error.HTTPError):
            if 400 <= error.code < 500 and error.code not in _RETRYABLE_HTTP_4XX:
                return (
                    f"The publisher returned HTTP {error.code} for this link — the PDF is "
                    "likely behind a subscription or login, or the link is dead."
                )
            return None  # 5xx / 408 / 429 may succeed on retry
        if isinstance(error, ValueError):
            # Raised by _validate_pdf and the size guards: the server responded,
            # but with something that is not a usable PDF.
            return (
                "The link did not return a valid PDF file — it may be a web page or an "
                "unsupported format rather than a downloadable paper."
            )
        return None

    def _validate_pdf(self, file_path: Path) -> None:
        """Validate that the downloaded file is a valid PDF."""
        # 1. Check size
        if file_path.stat().st_size < 100:
            raise ValueError("File too small to be a valid PDF.")

        # 2. Check Magic Bytes (%PDF- at start)
        with open(file_path, "rb") as f:
            header = f.read(4)
            if header != b"%PDF":
                raise ValueError("Invalid file signature: does not start with %PDF.")

        # 3. Attempt opening with PyMuPDF
        try:
            with fitz.open(file_path) as doc:
                if doc.page_count == 0:
                    raise ValueError("PDF has 0 pages.")
        except Exception as e:
            raise ValueError(f"Corrupted PDF or PyMuPDF could not parse: {e}") from e
