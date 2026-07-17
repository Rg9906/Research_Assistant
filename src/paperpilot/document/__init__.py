"""Document processing pipeline: extraction, chunking, and transformation."""

from paperpilot.document.downloader import PDFDownloader, normalize_pdf_url

__all__ = ["PDFDownloader", "normalize_pdf_url"]
