"""
Document chunking for the RAG pipeline.

Chunking is the process of splitting a document into smaller pieces (chunks)
that can be individually embedded and retrieved. It's one of the most
impactful decisions in a RAG system — arguably more important than the
choice of embedding model or vector database.

Why chunk at all?
    LLMs have limited context windows. Even with modern models that accept
    100K+ tokens, sending an entire 30-page research paper as context is
    wasteful and often counterproductive. The model gets overwhelmed by
    irrelevant text, and the answer quality drops.

    Instead, we embed small chunks independently, then retrieve only the
    most relevant ones for a given question. This is the "R" in RAG.

The chunk size trade-off:
    - Too large (2000+ chars): Each chunk contains too many topics. When we
      search for "attention mechanism," we get chunks that also discuss
      training details, datasets, etc. The signal is diluted.
    - Too small (100 chars): Each chunk lacks context. A sentence fragment
      like "the attention weights are computed" is meaningless without
      knowing what architecture is being discussed.
    - Sweet spot (500-1000 chars): Each chunk covers a coherent thought or
      paragraph, with enough context for meaningful retrieval.

Why overlap?
    Without overlap, information at chunk boundaries is lost. If a key
    sentence spans two chunks, neither chunk contains the complete thought.
    Overlap ensures that boundary sentences appear in at least one chunk
    in their entirety. 10-20% of chunk_size is typical.

Strategy: Recursive Character Splitting
    This is the most practical general-purpose strategy. It splits text by
    trying a hierarchy of separators:
    1. Double newline (paragraph breaks) — preferred
    2. Single newline (line breaks)
    3. Space (word boundaries)
    4. Empty string (character-level, last resort)

    At each level, if the resulting pieces are small enough, we're done.
    If a piece is still too large, we recurse with the next separator.
    This naturally respects document structure — paragraphs stay together
    when possible, sentences aren't split mid-word.

    This is the same strategy LangChain's RecursiveCharacterTextSplitter
    uses internally. We implement it ourselves first to understand the
    algorithm, then may switch to LangChain's implementation later when
    we adopt the framework.
"""

from __future__ import annotations

import logging
from uuid import UUID

from paperpilot.core.models import ChunkingStrategy, ExtractedPage, TextChunk

logger = logging.getLogger(__name__)

# Default separators in order of preference (most structure → least)
DEFAULT_SEPARATORS: list[str] = [
    "\n\n",  # Paragraph breaks
    "\n",    # Line breaks
    ". ",    # Sentence endings (note the space — avoids splitting "3.14")
    " ",     # Word boundaries
    "",      # Character-level (last resort)
]


def chunk_text(
    text: str,
    paper_id: UUID,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: list[str] | None = None,
    pages: list[ExtractedPage] | None = None,
) -> list[TextChunk]:
    """Split text into overlapping chunks using recursive character splitting.

    This is the main entry point for chunking. It takes the full text of a
    document and produces a list of TextChunk objects ready for embedding.

    Args:
        text: The full document text to chunk.
        paper_id: UUID of the paper this text belongs to (for linking chunks
                  back to their source document).
        chunk_size: Target maximum size of each chunk in characters.
        chunk_overlap: Number of characters to overlap between consecutive chunks.
        separators: Ordered list of separators to try. Defaults to
                    DEFAULT_SEPARATORS if not provided.
        pages: Optional list of ExtractedPage objects. If provided, chunks will
               include page number metadata (start_page, end_page).

    Returns:
        A list of TextChunk objects in document order.

    Raises:
        ValueError: If chunk_overlap >= chunk_size (no forward progress possible).
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be less than "
            f"chunk_size ({chunk_size})"
        )

    if not text.strip():
        logger.warning("Empty text provided for chunking")
        return []

    if separators is None:
        separators = DEFAULT_SEPARATORS

    # Step 1: Split text into raw string chunks
    raw_chunks = _recursive_split(text, chunk_size, separators)

    # Step 2: Merge small chunks and apply overlap
    merged_chunks = _merge_with_overlap(raw_chunks, chunk_size, chunk_overlap)

    # Step 3: Build a page-offset mapping for page number attribution
    page_map = _build_page_offset_map(pages) if pages else None

    # Step 4: Convert raw strings into TextChunk models with metadata
    text_chunks: list[TextChunk] = []
    current_offset = 0

    for i, chunk_text_content in enumerate(merged_chunks):
        # Determine which pages this chunk spans
        start_page = None
        end_page = None

        if page_map is not None:
            start_page = _find_page_for_offset(page_map, current_offset)
            end_page = _find_page_for_offset(
                page_map, current_offset + len(chunk_text_content) - 1
            )

        chunk = TextChunk(
            paper_id=paper_id,
            chunk_index=i,
            text=chunk_text_content,
            char_count=len(chunk_text_content),
            start_page=start_page,
            end_page=end_page,
            strategy=ChunkingStrategy.RECURSIVE_CHARACTER,
        )
        text_chunks.append(chunk)

        # Advance offset by the non-overlapping portion
        # (approximate — overlap means some chars appear in multiple chunks)
        current_offset += len(chunk_text_content) - chunk_overlap

    logger.info(
        "Chunking complete: %d chunks from %d characters "
        "(chunk_size=%d, overlap=%d)",
        len(text_chunks),
        len(text),
        chunk_size,
        chunk_overlap,
    )

    return text_chunks


def _recursive_split(
    text: str,
    chunk_size: int,
    separators: list[str],
) -> list[str]:
    """Recursively split text using a hierarchy of separators.

    The algorithm:
    1. Find the best separator — the first one that appears in the text.
    2. Split the text using that separator.
    3. For each piece:
       - If it fits within chunk_size, keep it.
       - If it's too large, recurse with the remaining separators.

    This naturally respects document structure: paragraph breaks are tried
    first, then line breaks, then sentence breaks, etc.

    Args:
        text: Text to split.
        chunk_size: Maximum size of each resulting piece.
        separators: Ordered list of separators (most preferred first).

    Returns:
        A list of text pieces, each at most chunk_size characters.
    """
    # Base case: text already fits
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # Find the best separator (first one that exists in the text)
    separator = ""
    remaining_separators = []

    for i, sep in enumerate(separators):
        if sep == "" or sep in text:
            separator = sep
            remaining_separators = separators[i + 1:]
            break

    # Split using the chosen separator
    if separator:
        pieces = text.split(separator)
    else:
        # This shouldn't happen since "" is always in the list, but just in case
        pieces = list(text)

    # Process each piece
    result: list[str] = []
    for piece in pieces:
        # Re-attach the separator (except for "" which is character-level)
        if separator and piece != pieces[-1]:
            piece_with_sep = piece + separator
        else:
            piece_with_sep = piece

        if not piece_with_sep.strip():
            continue

        if len(piece_with_sep) <= chunk_size:
            result.append(piece_with_sep)
        elif remaining_separators:
            # Piece is too large — recurse with finer separators
            result.extend(
                _recursive_split(piece_with_sep, chunk_size, remaining_separators)
            )
        else:
            # No more separators — force-split at chunk_size
            for start in range(0, len(piece_with_sep), chunk_size):
                sub = piece_with_sep[start : start + chunk_size]
                if sub.strip():
                    result.append(sub)

    return result


def _merge_with_overlap(
    pieces: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Merge small pieces into chunks and apply overlap between them.

    After recursive splitting, we often have many small pieces (individual
    sentences or paragraphs). This step merges consecutive small pieces
    until they approach chunk_size, then starts a new chunk with overlap
    from the previous one.

    Args:
        pieces: List of text pieces from _recursive_split.
        chunk_size: Target maximum chunk size.
        chunk_overlap: Characters to overlap between chunks.

    Returns:
        List of merged, overlapping chunks.
    """
    if not pieces:
        return []

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for piece in pieces:
        piece_len = len(piece)

        # If adding this piece would exceed chunk_size, finalize current chunk
        if current_length + piece_len > chunk_size and current_chunk:
            merged = "".join(current_chunk)
            chunks.append(merged.strip())

            # Start new chunk with overlap from the end of the current chunk
            overlap_text = merged[-chunk_overlap:] if chunk_overlap > 0 else ""
            current_chunk = [overlap_text, piece] if overlap_text else [piece]
            current_length = len(overlap_text) + piece_len
        else:
            current_chunk.append(piece)
            current_length += piece_len

    # Don't forget the last chunk
    if current_chunk:
        merged = "".join(current_chunk).strip()
        if merged:
            chunks.append(merged)

    return chunks


def _build_page_offset_map(pages: list[ExtractedPage]) -> list[tuple[int, int]]:
    """Build a mapping from character offset to page number.

    This lets us determine which page a chunk falls on, even after the
    full text has been concatenated.

    Returns:
        List of (cumulative_offset, page_number) tuples.
    """
    page_map: list[tuple[int, int]] = []
    cumulative = 0

    for page in pages:
        page_map.append((cumulative, page.page_number))
        # +2 for the "\n\n" separator used in get_full_text
        cumulative += page.char_count + 2

    return page_map


def _find_page_for_offset(
    page_map: list[tuple[int, int]],
    offset: int,
) -> int | None:
    """Find which page a given character offset falls on.

    Uses binary search logic via linear scan (fast enough for typical
    paper lengths of 5-50 pages).

    Args:
        page_map: Output of _build_page_offset_map.
        offset: Character offset into the full text.

    Returns:
        The 1-indexed page number, or None if offset is out of range.
    """
    if not page_map:
        return None

    result_page = page_map[0][1]

    for cumulative_offset, page_number in page_map:
        if cumulative_offset <= offset:
            result_page = page_number
        else:
            break

    return result_page
