"""Document Downloader for downloading and validating PDFs from academic URLs."""

from __future__ import annotations

import logging
import time
import urllib.request
from pathlib import Path
from uuid import UUID

import fitz

logger = logging.getLogger(__name__)


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


class PDFDownloader:
    """Handles downloading PDF files from external URLs, verifying validity, and retry logic."""

    def __init__(
        self, papers_dir: Path | str, timeout: float = 15.0, max_retries: int = 3
    ) -> None:
        """Initialize the downloader.

        Args:
            papers_dir: Directory where PDFs will be stored.
            timeout: Socket timeout for downloads in seconds.
            max_retries: Maximum download retry attempts.
        """
        self.papers_dir = Path(papers_dir)
        self.timeout = timeout
        self.max_retries = max_retries
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
                    # Write to temporary file first
                    with open(temp_path, "wb") as f:
                        f.write(response.read())

                # Validate PDF structure
                self._validate_pdf(temp_path)

                # Rename to final destination
                temp_path.rename(dest_path)
                logger.info("Successfully downloaded and validated PDF: %s", dest_path)
                return dest_path

            except Exception as e:
                # Clean up temp file on failure
                temp_path.unlink(missing_ok=True)
                logger.warning(
                    "Download attempt %d failed for URL %s: %s", attempt, normalized_url, e
                )

                if attempt >= self.max_retries:
                    logger.error("All download attempts failed for URL: %s", normalized_url)
                    raise RuntimeError(
                        f"Failed to download PDF from {normalized_url} after {self.max_retries} attempts."
                    ) from e

                # Backoff sleep
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError("Unexpected end of download loop.")

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
