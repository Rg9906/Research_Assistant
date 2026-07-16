"""
Core data models for PaperPilot AI.

These Pydantic models define the data contracts that flow through the entire
system. Every agent, pipeline step, and storage layer imports from here.

Design decisions:
    - All models inherit from pydantic.BaseModel for automatic validation,
      serialization, and schema generation.
    - Fields use descriptive types and constraints rather than raw primitives.
    - Optional fields have explicit defaults — no ambiguity about what's missing.
    - Models are immutable by default (frozen=True) where appropriate to prevent
      accidental mutation of shared data.

Why Pydantic?
    Pydantic solves a fundamental problem in data-heavy systems: ensuring that
    data flowing between components has the correct shape, types, and constraints.
    Without it, you'd write manual validation code everywhere or (worse) discover
    type mismatches at runtime deep inside an LLM call.

    Pydantic v2 is built on top of Rust (via pydantic-core), making validation
    extremely fast — roughly 5-50x faster than v1. It also generates JSON Schema
    automatically, which is useful for API documentation and LLM tool definitions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PaperSource(str, Enum):
    """Where a paper was discovered.

    Using an enum instead of a raw string prevents typos and makes it easy to
    add new sources later. The str mixin lets us serialize directly to JSON
    as a string value (e.g., "semantic_scholar") rather than an integer.
    """

    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    MANUAL = "manual"  # User uploaded a PDF directly


class ChunkingStrategy(str, Enum):
    """Which chunking algorithm produced a given chunk.

    Tracking this lets us compare retrieval quality across strategies later
    without re-processing documents.
    """

    RECURSIVE_CHARACTER = "recursive_character"
    # Future strategies:
    # SEMANTIC = "semantic"           # Split by semantic similarity
    # SECTION_BASED = "section_based" # Split by detected headings


# ---------------------------------------------------------------------------
# Paper Metadata
# ---------------------------------------------------------------------------

class PaperMetadata(BaseModel):
    """Metadata about a single research paper.

    This model matches the metadata fields specified in the project document
    (Phase 1): title, authors, year, citations, abstract, DOI, PDF link,
    source, venue, and keywords.

    It is the first thing created when a paper is discovered by the Search
    Agent and persists through the entire pipeline. Downstream components
    (Retrieval Agent, Summarizer, Memory) all reference this model.

    Attributes:
        paper_id: Unique identifier for this paper within PaperPilot.
                  Generated automatically; NOT the same as DOI or arXiv ID.
        title: The paper's title.
        authors: List of author names.
        publication_year: Year the paper was published.
        citation_count: Number of citations (from the discovery source).
        abstract: The paper's abstract text.
        doi: Digital Object Identifier (globally unique paper identifier).
        pdf_url: URL where the PDF can be downloaded.
        source: Which academic database this paper was discovered from.
        venue: Conference or journal where the paper was published.
        keywords: Author-provided or system-extracted keywords.
        discovered_at: When PaperPilot first found this paper.
    """

    paper_id: UUID = Field(default_factory=uuid4)
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    citation_count: int | None = None
    abstract: str | None = None
    doi: str | None = None
    pdf_url: str | None = None
    source: PaperSource = PaperSource.MANUAL
    venue: str | None = None
    keywords: list[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=datetime.now)

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# Extracted Page
# ---------------------------------------------------------------------------

class ExtractedPage(BaseModel):
    """A single page of extracted text from a PDF.

    We preserve page boundaries because:
    1. Citations and section references use page numbers.
    2. Some chunking strategies may want to respect page boundaries.
    3. It helps with debugging — if a chunk produces bad results, we can
       trace back to the exact page.

    Attributes:
        page_number: 1-indexed page number within the PDF.
        text: The raw extracted text content of this page.
        char_count: Number of characters on this page.
    """

    page_number: int = Field(ge=1)
    text: str
    char_count: int = Field(ge=0)

    model_config = {"frozen": True}

    @classmethod
    def from_text(cls, page_number: int, text: str) -> ExtractedPage:
        """Factory method that auto-computes char_count."""
        return cls(page_number=page_number, text=text, char_count=len(text))


# ---------------------------------------------------------------------------
# Text Chunk
# ---------------------------------------------------------------------------

class TextChunk(BaseModel):
    """A chunk of text ready to be embedded and stored in a vector database.

    This is the atomic unit of retrieval in the RAG pipeline. When a user asks
    a question, the retriever finds the most relevant TextChunks and passes
    them as context to the LLM.

    Chunk quality directly determines retrieval quality. If chunks are too
    large, they dilute the signal with irrelevant text. If too small, they
    lose context. The typical sweet spot for research papers is 500-1000
    characters with 100-200 character overlap.

    Attributes:
        chunk_id: Unique identifier for this chunk.
        paper_id: Which paper this chunk belongs to (foreign key to PaperMetadata).
        chunk_index: Position of this chunk within the document (0-indexed).
        text: The chunk's text content.
        char_count: Number of characters in this chunk.
        start_page: The page where this chunk's text begins.
        end_page: The page where this chunk's text ends.
        strategy: Which chunking algorithm produced this chunk.
        metadata: Arbitrary additional metadata (e.g., detected section heading).
    """

    chunk_id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_index: int = Field(ge=0)
    text: str
    char_count: int = Field(ge=0)
    start_page: int | None = None
    end_page: int | None = None
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE_CHARACTER
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Processed Document
# ---------------------------------------------------------------------------

class ProcessedDocument(BaseModel):
    """The complete result of running a PDF through the document processing pipeline.

    This is the contract between the document processing module and everything
    downstream: the embedding engine, the vector store, the summarizer agent,
    and the tutor agent.

    A ProcessedDocument contains:
    1. The paper's metadata (who wrote it, where it was published, etc.)
    2. The full extracted text (for summarization and full-text operations)
    3. Individual pages (for page-level reference)
    4. Chunks (for embedding and retrieval)

    Attributes:
        metadata: The paper's bibliographic metadata.
        source_path: Local filesystem path to the downloaded PDF.
        full_text: The entire extracted text concatenated.
        pages: List of extracted pages preserving page boundaries.
        chunks: List of text chunks ready for embedding.
        processed_at: When this document was processed.
        total_pages: Total number of pages in the PDF.
        total_chars: Total character count of extracted text.
    """

    metadata: PaperMetadata
    source_path: Path | None = None
    full_text: str = ""
    pages: list[ExtractedPage] = Field(default_factory=list)
    chunks: list[TextChunk] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=datetime.now)
    total_pages: int = Field(ge=0, default=0)
    total_chars: int = Field(ge=0, default=0)


# ---------------------------------------------------------------------------
# Retrieval Result
# ---------------------------------------------------------------------------

class RetrievalResult(BaseModel):
    """A text chunk retrieved by similarity search, with its relevance score.

    This is the output of the retrieval pipeline. It wraps a TextChunk with
    query-specific information: how similar the chunk is to the query, and
    its rank among all results.

    Why not add the score to TextChunk directly?
        Scores are query-dependent — the same chunk has different scores for
        different queries. TextChunk is immutable and represents the document
        content. RetrievalResult represents a specific retrieval event.
        This separation follows the Single Responsibility Principle.

    Attributes:
        chunk: The retrieved text chunk.
        score: Similarity score (L2 distance for FAISS — lower = more similar).
        rank: 1-indexed position in the results (1 = most relevant).
    """

    chunk: TextChunk
    score: float
    rank: int = Field(ge=1)

    model_config = {"frozen": True}

