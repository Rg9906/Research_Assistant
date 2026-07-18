"""Document ingestion using LlamaIndex SimpleDirectoryReader and existing PDFDownloader."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Any

from llama_index.core import SimpleDirectoryReader, Document
from paperpilot.core.models import PaperMetadata
from paperpilot.document.downloader import PDFDownloader
from paperpilot.config import get_settings

logger = logging.getLogger(__name__)


class PaperIngestionService:
    """Ingests research paper PDFs into LlamaIndex Document instances with rich metadata."""

    def __init__(self, downloader: PDFDownloader | None = None) -> None:
        if downloader:
            self.downloader = downloader
        else:
            settings = get_settings()
            self.downloader = PDFDownloader(papers_dir=settings.papers_dir)

    def download_and_load(self, metadata: PaperMetadata, pdf_url: str | None = None) -> List[Document]:
        """Download paper PDF using existing downloader and load via SimpleDirectoryReader.

        Attaches paper metadata (paper_id, title, authors, DOI, arXiv ID, etc.)
        to each loaded Document object for grounded retrieval and future citations.
        """
        url_to_use = pdf_url or metadata.pdf_url
        if not url_to_use:
            raise ValueError(f"No PDF URL provided for paper '{metadata.title}' ({metadata.paper_id})")

        pdf_path = self.downloader.download_pdf(paper_id=metadata.paper_id, pdf_url=url_to_use)

        reader = SimpleDirectoryReader(input_files=[str(pdf_path)])
        documents = reader.load_data()

        authors_str = (
            ", ".join(metadata.authors)
            if isinstance(metadata.authors, list)
            else str(metadata.authors or "")
        )

        for doc in documents:
            doc.metadata.update({
                "paper_id": str(metadata.paper_id),
                "title": metadata.title,
                "authors": authors_str,
                "publication_year": metadata.publication_year or "",
                "doi": metadata.doi or "",
                "venue": metadata.venue or "",
                "pdf_url": url_to_use,
                "filename": pdf_path.name,
            })

        logger.info(
            "Loaded %d LlamaIndex document pages for paper '%s' from %s",
            len(documents),
            metadata.title,
            pdf_path,
        )
        return documents
