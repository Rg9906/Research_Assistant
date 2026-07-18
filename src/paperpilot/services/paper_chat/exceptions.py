"""Domain exceptions for PaperPilot AI Document Intelligence layer."""

from __future__ import annotations


class PaperChatException(Exception):
    """Base exception for Paper Chat service operations."""
    pass


class PDFDownloadError(PaperChatException):
    """Raised when downloading a paper PDF fails or times out."""
    pass


class PDFParseError(PaperChatException):
    """Raised when PyMuPDF or fallback readers cannot parse a PDF file."""
    pass


class IndexBuildError(PaperChatException):
    """Raised when building or embedding a LlamaIndex index fails."""
    pass


class IndexLoadError(PaperChatException):
    """Raised when loading an existing LlamaIndex from storage fails."""
    pass


class QueryExecutionError(PaperChatException):
    """Raised when executing a query or chat request fails."""
    pass
