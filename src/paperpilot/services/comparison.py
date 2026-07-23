"""Multi-paper comparison: retrieve per paper -> ComparisonAgent -> Critic audit.

Why this module exists:
    CLAUDE.md's roadmap names "a Comparison agent over `retrieve_across_papers`"
    as the natural next vision feature once grounded QA (services/grounded_qa.py)
    was in place. This is that feature. It deliberately reuses everything it
    can rather than building a second retrieval or audit path:

        for each paper: retrieve_across_papers([paper], axis)  # Stack B, per-paper
          -> TextChunk contracts (core/models.py)
          -> ComparisonAgent : structured per-paper breakdown + synthesis
          -> CriticAgent     : the same grounding/relevance/style audit chat uses
          -> [rejected]       : retry with feedback, up to max_retries

    Comparison retrieves per paper (not merged-by-score like MultiPaperRetriever)
    because a comparison claim must be attributable to the paper it came from —
    merging by score would lose that provenance.

    A comparison turn is appended to the same chat_history a workspace's regular
    chat uses (via grounded_qa.append_chat_turn), so a follow-up question like
    "now compare their limitations too" can reference it.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from llama_index.core.llms import ChatMessage
from pydantic import BaseModel, Field

from paperpilot.agent.comparison import ComparisonAgent, ComparisonReport
from paperpilot.agent.critic import CriticAgent, CritiqueReport
from paperpilot.core.models import PaperMetadata
from paperpilot.services.grounded_qa import append_chat_turn, nodes_to_chunks
from paperpilot.services.paper_chat.session import PaperSessionManager, build_citations

logger = logging.getLogger(__name__)


class ComparisonAnswer(BaseModel):
    """The result of one comparison turn, mirroring GroundedAnswer's shape.

    Sharing GroundedAnswer's fields (approved/refused/attempts/critique/
    chat_history) lets the API layer treat a comparison response uniformly
    with a chat response instead of inventing a parallel contract.
    """

    sections: List[dict] = Field(default_factory=list)
    synthesis: str = ""
    citations: List[dict] = Field(default_factory=list)
    approved: bool = Field(description="True if the critic approved the synthesis.")
    refused: bool = Field(description="True if fewer than two papers had usable context.")
    attempts: int = Field(ge=1, description="How many comparison generations were needed.")
    critique: Optional[CritiqueReport] = None
    chat_history: List[object] = Field(default_factory=list, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


def _render_for_audit(report: ComparisonReport) -> str:
    """Flatten a structured ComparisonReport into plain text for the Critic.

    The critic audits a single answer string against context, the same
    contract used for chat — it doesn't need to know about the sections/
    synthesis split, so this is the one place that flattens it.
    """
    parts = [f"{s.title}: {s.summary}" for s in report.sections]
    parts.append(f"Synthesis: {report.synthesis}")
    return "\n\n".join(parts)


class ComparisonService:
    """Compares 2+ workspace papers along an axis, audited the same way chat is.

    Dependencies are injected (CLAUDE.md §6) so tests can supply stub chat
    models and a stub session manager without touching the network.
    """

    def __init__(
        self,
        session_manager: PaperSessionManager,
        comparison_agent: ComparisonAgent,
        critic: CriticAgent,
        max_retries: int = 2,
        critique_enabled: bool = True,
    ) -> None:
        self.session_manager = session_manager
        self.comparison_agent = comparison_agent
        self.critic = critic
        self.max_retries = max(0, max_retries)
        self.critique_enabled = critique_enabled
        logger.info(
            "ComparisonService initialized (max_retries=%d, critique=%s)",
            self.max_retries,
            "on" if critique_enabled else "off",
        )

    def compare(
        self,
        papers: List[PaperMetadata],
        axis: str,
        chat_history: Optional[List[ChatMessage]] = None,
        difficulty: str = "graduate/expert",
        similarity_top_k: Optional[int] = None,
    ) -> ComparisonAnswer:
        """Compare `papers` along `axis`, retrieving context independently per paper.

        Args:
            papers: The papers to compare (2 or more expected).
            axis: The comparison dimension, e.g. "methodology", or free text.
            chat_history: Prior turns for this workspace's conversation.
            difficulty: Explanation level passed to both the agent and critic.
            similarity_top_k: Override how many chunks to retrieve per paper.

        Returns:
            A ComparisonAnswer. Refuses immediately (no retrieval, no LLM call)
            if fewer than two papers are given.
        """
        history = list(chat_history or [])

        if len(papers) < 2:
            logger.info("Comparison requires at least 2 papers; got %d. Refusing.", len(papers))
            return ComparisonAnswer(
                synthesis="Select at least two papers to compare.",
                approved=False,
                refused=True,
                attempts=1,
                chat_history=history,
            )

        papers_chunks: dict[str, tuple[str, list]] = {}
        all_citations: List[dict] = []
        for paper in papers:
            nodes = self.session_manager.retrieve_across_papers(
                [paper], axis, similarity_top_k=similarity_top_k
            )
            chunks = nodes_to_chunks(nodes)
            papers_chunks[str(paper.paper_id)] = (paper.title, chunks)
            all_citations.extend(build_citations(nodes, default_paper_id=paper.paper_id))

        all_chunks = [chunk for _, chunks in papers_chunks.values() for chunk in chunks]

        prompt_axis = axis
        report: Optional[ComparisonReport] = None
        critique: Optional[CritiqueReport] = None

        for attempt in range(1, self.max_retries + 2):
            report = self.comparison_agent.compare(prompt_axis, papers_chunks, difficulty=difficulty)

            if report.refused:
                logger.info("ComparisonAgent refused: not enough usable context per paper.")
                return ComparisonAnswer(
                    synthesis="Not enough content was found for at least two of the selected papers.",
                    approved=False,
                    refused=True,
                    attempts=attempt,
                    chat_history=history,
                )

            rendered = _render_for_audit(report)
            turn_text = f"Compare {len(papers)} papers on: {axis}"

            if not self.critique_enabled:
                return ComparisonAnswer(
                    sections=[s.model_dump() for s in report.sections],
                    synthesis=report.synthesis,
                    citations=all_citations,
                    approved=True,
                    refused=False,
                    attempts=attempt,
                    chat_history=append_chat_turn(history, turn_text, rendered),
                )

            try:
                critique = self.critic.evaluate_answer(axis, all_chunks, rendered, difficulty=difficulty)
            except Exception as e:  # noqa: BLE001
                logger.warning("Critic unavailable for comparison, returning unaudited: %s", e)
                return ComparisonAnswer(
                    sections=[s.model_dump() for s in report.sections],
                    synthesis=report.synthesis,
                    citations=all_citations,
                    approved=False,
                    refused=False,
                    attempts=attempt,
                    critique=CritiqueReport(
                        grounding_passed=False,
                        grounding_feedback="Audit did not run.",
                        relevance_passed=False,
                        relevance_feedback="Audit did not run.",
                        style_passed=False,
                        style_feedback="Audit did not run.",
                        approved=False,
                        feedback=f"REJECTED: the grounding audit could not be completed ({type(e).__name__}).",
                    ),
                    chat_history=append_chat_turn(history, turn_text, rendered),
                )

            if critique.approved:
                logger.info("Comparison approved by critic on attempt %d.", attempt)
                return ComparisonAnswer(
                    sections=[s.model_dump() for s in report.sections],
                    synthesis=report.synthesis,
                    citations=all_citations,
                    approved=True,
                    refused=False,
                    attempts=attempt,
                    critique=critique,
                    chat_history=append_chat_turn(history, turn_text, rendered),
                )

            logger.warning(
                "Critic rejected comparison on attempt %d/%d: %s",
                attempt,
                self.max_retries + 1,
                critique.feedback,
            )
            prompt_axis = (
                f"{axis}\n\n[Reviewer feedback on your previous attempt, which was REJECTED: "
                f"{critique.feedback}\nProduce a corrected comparison that resolves every issue "
                "above, still using ONLY the Source Context provided.]"
            )

        # Retries exhausted: return the last attempt, flagged, with its critique.
        logger.warning("Returning unapproved comparison after %d attempts.", self.max_retries + 1)
        rendered = _render_for_audit(report)
        return ComparisonAnswer(
            sections=[s.model_dump() for s in report.sections],
            synthesis=report.synthesis,
            citations=all_citations,
            approved=False,
            refused=False,
            attempts=self.max_retries + 1,
            critique=critique,
            chat_history=append_chat_turn(history, f"Compare {len(papers)} papers on: {axis}", rendered),
        )
