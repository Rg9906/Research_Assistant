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
