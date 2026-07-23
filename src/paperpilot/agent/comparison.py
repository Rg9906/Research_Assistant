"""Comparison Agent for contrasting multiple papers along one axis.

Why a separate agent rather than reusing the Tutor?
    The Tutor answers one question from one merged pool of chunks and returns
    plain text. A comparison needs to keep each paper's evidence separate (so
    a claim can be attributed to the paper it came from) and produce a
    structured result (a per-paper breakdown plus a synthesis), so it gets its
    own JSON contract — following the same shape as CriticAgent rather than
    TutorAgent's plain-text one.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from paperpilot.agent.formatting import clean_json_markdown, format_chunks_grouped_by_paper
from paperpilot.core.models import TextChunk

logger = logging.getLogger(__name__)


class PaperComparisonSection(BaseModel):
    """One paper's contribution to a comparison along the requested axis."""

    paper_id: str
    title: str
    summary: str


class ComparisonReport(BaseModel):
    """The structured result of comparing 2+ papers along one axis."""

    sections: list[PaperComparisonSection] = Field(default_factory=list)
    synthesis: str = ""
    refused: bool = Field(
        default=False,
        description="True if fewer than two papers had usable context for this axis.",
    )


COMPARISON_SYSTEM_PROMPT = (
    "You are an AI research assistant comparing multiple papers for a researcher. "
    "You are given Source Context blocks grouped by paper, and a comparison axis.\n\n"
    "Explanation Style Guideline:\n"
    "{difficulty_instruction}\n\n"
    "Constraints:\n"
    "1. Rely ONLY on the provided Source Context for each paper. Do not assume, "
    "extrapolate, or use outside knowledge about these papers.\n"
    "2. For each paper, write a short summary of what that paper's context says about "
    "the comparison axis: '{axis}'. If a paper's context says nothing relevant to the "
    "axis, say so plainly in that paper's summary rather than inventing content.\n"
    "3. Then write a synthesis paragraph that directly contrasts the papers along the "
    "axis — where they agree, where they differ, and how.\n"
    "4. When reference details are available (such as page numbers), cite them "
    "(e.g., [Page 3]).\n\n"
    "Respond strictly as a JSON object matching this schema:\n"
    "{{\n"
    "  \"sections\": [{{\"paper_id\": \"...\", \"title\": \"...\", \"summary\": \"...\"}}, ...],\n"
    "  \"synthesis\": \"...\",\n"
    "  \"refused\": false\n"
    "}}"
)


class ComparisonAgent:
    """Compares multiple papers along a user- or system-supplied axis.

    Attributes:
        chat_model: The LangChain ChatModel instance used for generation.
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model
        logger.info("ComparisonAgent initialized.")

    def compare(
        self,
        axis: str,
        papers_chunks: dict[str, tuple[str, list[TextChunk]]],
        difficulty: str = "graduate/expert",
    ) -> ComparisonReport:
        """Compare the given papers' retrieved chunks along `axis`.

        Args:
            axis: The comparison dimension, e.g. "methodology" or free text.
            papers_chunks: Maps paper_id (str) to (title, chunks) for that
                paper. Papers with no chunks are dropped before comparing.
            difficulty: Explanation level, same vocabulary as TutorAgent.

        Returns:
            A ComparisonReport. `refused=True` (with empty sections/synthesis)
            if fewer than two papers had any usable context — comparing one
            paper against nothing is not a comparison.
        """
        usable = {pid: (title, chunks) for pid, (title, chunks) in papers_chunks.items() if chunks}
        if len(usable) < 2:
            logger.warning(
                "ComparisonAgent: only %d paper(s) had usable context; refusing.", len(usable)
            )
            return ComparisonReport(refused=True)

        context_str = format_chunks_grouped_by_paper(usable)
        difficulty_instruction = {
            "beginner": "Explain simply, using clear language and everyday analogies.",
            "undergraduate": "Explain at an undergraduate level: accurate but accessible.",
            "graduate/expert": "Explain at a graduate/researcher level: precise, detailed, rigorous.",
        }.get(difficulty.lower(), "Explain at a graduate/researcher level: precise, detailed, rigorous.")

        system_text = COMPARISON_SYSTEM_PROMPT.format(
            difficulty_instruction=difficulty_instruction, axis=axis
        )
        prompt = f"Source Context (grouped by paper):\n{context_str}\n\nComparison axis: {axis}"

        messages = [SystemMessage(content=system_text), HumanMessage(content=prompt)]

        logger.info("ComparisonAgent comparing %d papers on axis '%s'", len(usable), axis)
        response = self.chat_model.invoke(messages)
        content = str(response.content).strip()
        cleaned_content = clean_json_markdown(content)

        try:
            report = ComparisonReport.model_validate_json(cleaned_content)
            logger.info("ComparisonAgent produced %d section(s).", len(report.sections))
            return report
        except Exception as e:
            logger.error(
                "ComparisonAgent failed to parse structured report: %s. Raw content: %s", e, content
            )
            # Fall back to treating the whole response as an unstructured
            # synthesis rather than losing the answer entirely.
            return ComparisonReport(sections=[], synthesis=content, refused=False)
