"""Shared formatting helpers for LLM-facing agents.

Both the Tutor and Critic agents turn a list of retrieved TextChunks into the
same "Chunk N (Page X):\\n<text>" context block, and both the Planner and
Critic agents strip markdown code-fences from an LLM's JSON response before
parsing it. Centralizing these avoids the two agents drifting out of sync
when one gets edited without the other.
"""

from __future__ import annotations

from paperpilot.core.models import TextChunk


def format_chunks_as_context(chunks: list[TextChunk]) -> str:
    """Format retrieved chunks into a labeled context block for LLM prompts."""
    formatted_blocks = []
    for chunk in chunks:
        page_info = f" (Page {chunk.start_page})" if chunk.start_page else ""
        block = f"Chunk {chunk.chunk_index}{page_info}:\n{chunk.text.strip()}"
        formatted_blocks.append(block)
    return "\n\n-----------------------------------------\n\n".join(formatted_blocks)


def format_chunks_grouped_by_paper(papers_chunks: dict[str, tuple[str, list[TextChunk]]]) -> str:
    """Format chunks from multiple papers into one context block, labeled by source.

    Comparison needs to know which chunk came from which paper — unlike chat's
    merged-by-score retrieval, a comparison claim must be attributable to a
    specific paper. This is the per-paper analogue of `format_chunks_as_context`.

    Args:
        papers_chunks: Maps paper_id (str) to (title, chunks) for that paper.
    """
    paper_blocks = []
    for paper_id, (title, chunks) in papers_chunks.items():
        context = format_chunks_as_context(chunks)
        paper_blocks.append(f"=== {title} (paper_id: {paper_id}) ===\n{context}")
    return "\n\n=========================================\n\n".join(paper_blocks)


def clean_json_markdown(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` markdown code-fence markers if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
