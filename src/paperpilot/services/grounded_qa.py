"""Grounded question answering: the Tutor/Critic contract applied to real traffic.

Why this module exists:
    PaperPilot had two disconnected answers to "answer a question about a
    paper" (CLAUDE.md §4). Stack B (LlamaIndex `PaperSession`) served all
    production traffic but generated with LlamaIndex's default chat prompts —
    no explicit grounding instruction, no refusal string, no audit. Stack A
    (`agent/tutor.py`, `agent/critic.py`) implemented exactly the grounding and
    self-critique contract the project's vision demands ("No hallucinated
    answers should be produced whenever possible") but no endpoint invoked it.

    This service is the join. It uses Stack B for what Stack B is good at —
    document loading, indexing, persistence, multi-paper retrieval — and Stack
    A for generation and verification:

        retrieve (MultiPaperRetriever)
          -> TextChunk contracts (core/models.py)
          -> TutorAgent  : answer using ONLY these chunks, else refuse
          -> CriticAgent : audit grounding / relevance / style
          -> [rejected]  : retry with the critic's feedback, up to max_retries

    It deliberately does not introduce a third RAG implementation: retrieval is
    delegated to `PaperSessionManager.retrieve_across_papers`, which is the same
    code path the default chat endpoint uses.

Why retries are bounded:
    Each retry is two more LLM calls (tutor + critic), so an unbounded loop is
    both slow and expensive. After the last attempt the best answer is returned
    with `approved=False` rather than raising — a flagged answer the user can
    judge is more useful than an error, and the critique travels with it.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from uuid import UUID

from llama_index.core.llms import ChatMessage
from llama_index.core.schema import NodeWithScore
from pydantic import BaseModel, Field

from paperpilot.agent.critic import CriticAgent, CritiqueReport
from paperpilot.agent.tutor import TutorAgent
from paperpilot.core.models import PaperMetadata, TextChunk
from paperpilot.services.paper_chat.session import (
    PaperSessionManager,
    build_citations,
    extract_page_number,
)

logger = logging.getLogger(__name__)

#: How many previous turns to feed the question-condensing step. Two turns is
#: enough to resolve "it"/"that" in a follow-up without spending context (and
#: latency) replaying an entire conversation on every question.
_CONDENSE_HISTORY_TURNS = 4

CONDENSE_PROMPT = (
    "Given the conversation below and a follow-up question, rewrite the follow-up "
    "as a standalone question that can be understood without the conversation. "
    "Resolve any pronouns or references to earlier turns. "
    "Do not answer the question. Return ONLY the rewritten question.\n\n"
    "Conversation:\n{history}\n\n"
    "Follow-up question: {question}\n\n"
    "Standalone question:"
)


class GroundedAnswer(BaseModel):
    """The result of one grounded QA turn, including its own audit trail.

    The critique is returned rather than hidden so the API (and ultimately the
    user) can see *why* an answer was approved or flagged. That transparency is
    the point of having a critic at all.
    """

    answer: str
    citations: List[dict] = Field(default_factory=list)
    approved: bool = Field(description="True if the critic approved the final answer.")
    refused: bool = Field(description="True if the tutor found no grounding and refused.")
    attempts: int = Field(ge=1, description="How many tutor generations were needed.")
    critique: Optional[CritiqueReport] = None
    chat_history: List[Any] = Field(default_factory=list, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


def nodes_to_chunks(nodes: List[NodeWithScore]) -> List[TextChunk]:
    """Adapt LlamaIndex retrieval output to the project's TextChunk contract.

    The agents are written against `core/models.py` (CLAUDE.md §6: Pydantic as
    the contract layer) and know nothing about LlamaIndex — that decoupling is
    what lets the same Tutor work over any retriever. This is the single
    translation point between the two.

    Metadata values are coerced to `str` because `TextChunk.metadata` is typed
    `dict[str, str]` while LlamaIndex node metadata legitimately contains ints
    (e.g. `publication_year`) — passing it through raw used to crash on any
    paper with a year (CLAUDE.md §7).
    """
    chunks: List[TextChunk] = []
    for index, node_with_score in enumerate(nodes):
        node = node_with_score.node
        meta = node.metadata or {}

        raw_paper_id = meta.get("paper_id")
        try:
            paper_id = UUID(str(raw_paper_id))
        except (TypeError, ValueError):
            # A node with no usable paper_id can still be quoted as evidence;
            # losing the whole chunk would be a worse failure than losing its
            # provenance, so synthesize an id rather than dropping it.
            logger.warning("Retrieved node %s has no valid paper_id metadata", node.node_id)
            paper_id = UUID(int=0)

        # Same extraction the citations use, so the page the Tutor is told to
        # cite is the page the UI shows next to the answer.
        page = extract_page_number(meta)
        try:
            page_num = int(page) if page is not None else None
        except (TypeError, ValueError):
            page_num = None

        text = node.get_content()
        chunks.append(
            TextChunk(
                paper_id=paper_id,
                chunk_index=index,
                text=text,
                char_count=len(text),
                start_page=page_num,
                end_page=page_num,
                metadata={str(k): str(v) for k, v in meta.items()},
            )
        )
    return chunks


class GroundedQAService:
    """Answers workspace questions with retrieval → grounded generation → audit.

    Dependencies are injected (CLAUDE.md §6) so tests can supply stub chat
    models and a stub retriever without touching the network.
    """

    def __init__(
        self,
        session_manager: PaperSessionManager,
        tutor: TutorAgent,
        critic: CriticAgent,
        max_retries: int = 2,
        critique_enabled: bool = True,
    ) -> None:
        self.session_manager = session_manager
        self.tutor = tutor
        self.critic = critic
        self.max_retries = max(0, max_retries)
        # The audit re-sends the full context, so it roughly doubles the tokens
        # per answer. On a small per-minute quota that is the difference between
        # a working app and a 429 on every second question, so it can be turned
        # off — answers are still written under the Tutor's grounding contract
        # and still refuse when unsupported; they are simply unaudited.
        self.critique_enabled = critique_enabled
        logger.info(
            "GroundedQAService initialized (max_retries=%d, critique=%s)",
            self.max_retries,
            "on" if critique_enabled else "off",
        )

    def _condense_question(self, question: str, chat_history: List[ChatMessage]) -> str:
        """Rewrite a follow-up into a standalone question for retrieval.

        Retrieval is embedding similarity against the question text, so a
        follow-up like "why does that matter?" retrieves almost nothing useful
        on its own — the subject lives in the previous turn. The condensed
        question is used only for *retrieval*; the user's original wording is
        what the Tutor answers, so nothing is lost if the rewrite is imperfect.
        """
        if not chat_history:
            return question

        recent = chat_history[-_CONDENSE_HISTORY_TURNS:]
        history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
        prompt = CONDENSE_PROMPT.format(history=history_text, question=question)

        try:
            response = self.tutor.chat_model.invoke(prompt)
            condensed = str(response.content).strip()
            if condensed:
                logger.info("Condensed follow-up to: '%s'", condensed)
                return condensed
        except Exception as e:
            # Never fail a question because the rewrite failed — the raw
            # question is a valid, if weaker, retrieval query.
            logger.warning("Question condensing failed, using raw question: %s", e)
        return question

    def _revision_request(self, question: str, feedback: str) -> str:
        """Fold the critic's rejection back into the next tutor attempt."""
        return (
            f"{question}\n\n"
            "[Reviewer feedback on your previous attempt, which was REJECTED: "
            f"{feedback}\n"
            "Produce a corrected answer that resolves every issue above, still using "
            "ONLY the Source Context provided.]"
        )

    def answer(
        self,
        papers: List[PaperMetadata],
        question: str,
        chat_history: Optional[List[ChatMessage]] = None,
        difficulty: str = "graduate/expert",
        retrieval_query: Optional[str] = None,
        similarity_top_k: Optional[int] = None,
        apply_similarity_cutoff: bool = True,
    ) -> GroundedAnswer:
        """Answer `question` grounded in `papers`, auditing before returning.

        Args:
            papers: Every paper in the workspace — retrieval fans out across all.
            question: The user's question, in their own words.
            chat_history: Prior turns for this conversation (owned by the caller,
                same contract as PaperSession.chat).
            difficulty: Explanation level passed to both tutor and critic.
            retrieval_query: Search the index with this instead of the question.
                For instruction-shaped prompts ("summarize this paper") the
                question makes a poor embedding query — see SummarizerService.
            similarity_top_k: Override how many chunks to retrieve.
            apply_similarity_cutoff: Disable to keep chunks the relevance filter
                would drop — required for whole-document tasks.

        Returns:
            A GroundedAnswer carrying the answer, its citations, and its audit.
        """
        if not papers:
            raise ValueError("answer() requires at least one paper.")

        history = list(chat_history or [])
        if retrieval_query is None:
            retrieval_query = self._condense_question(question, history)

        nodes = self.session_manager.retrieve_across_papers(
            papers,
            retrieval_query,
            similarity_top_k=similarity_top_k,
            apply_postprocessors=apply_similarity_cutoff,
        )
        chunks = nodes_to_chunks(nodes)
        citations = build_citations(nodes)

        if not chunks:
            # Retrieval found nothing above the similarity threshold. Refusing
            # here saves two LLM calls that could only produce an ungrounded
            # answer, and matches what the Tutor would return anyway.
            logger.info("No chunks passed retrieval filtering; refusing to answer.")
            return GroundedAnswer(
                answer=self.tutor.refusal_response,
                citations=[],
                approved=False,
                refused=True,
                attempts=1,
                chat_history=history,
            )

        answer = ""
        report: Optional[CritiqueReport] = None
        prompt_question = question

        for attempt in range(1, self.max_retries + 2):
            answer = self.tutor.answer_question(prompt_question, chunks, difficulty=difficulty)

            if answer.strip() == self.tutor.refusal_response.strip():
                logger.info("Tutor refused: context did not support an answer.")
                return GroundedAnswer(
                    answer=answer,
                    citations=citations,
                    approved=False,
                    refused=True,
                    attempts=attempt,
                    chat_history=self._append_turn(history, question, answer),
                )

            if not self.critique_enabled:
                return GroundedAnswer(
                    answer=answer,
                    citations=citations,
                    approved=True,  # nothing rejected it; the audit was not run
                    refused=False,
                    attempts=attempt,
                    chat_history=self._append_turn(history, question, answer),
                )

            try:
                report = self.critic.evaluate_answer(question, chunks, answer, difficulty=difficulty)
            except Exception as e:  # noqa: BLE001
                # The audit costs a second full-context call, so it is the most
                # likely thing to hit a rate/token limit — and losing a good
                # answer that the tutor already produced (and the user already
                # waited for) because the *reviewer* was throttled is the wrong
                # trade. Return it unverified and say so, rather than raising.
                logger.warning("Critic unavailable, returning unaudited answer: %s", e)
                return GroundedAnswer(
                    answer=answer,
                    citations=citations,
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
                    chat_history=self._append_turn(history, question, answer),
                )

            if report.approved:
                logger.info("Answer approved by critic on attempt %d.", attempt)
                return GroundedAnswer(
                    answer=answer,
                    citations=citations,
                    approved=True,
                    refused=False,
                    attempts=attempt,
                    critique=report,
                    chat_history=self._append_turn(history, question, answer),
                )

            logger.warning(
                "Critic rejected answer on attempt %d/%d: %s",
                attempt,
                self.max_retries + 1,
                report.feedback,
            )
            prompt_question = self._revision_request(question, report.feedback)

        # Retries exhausted: return the last attempt, flagged, with its critique.
        logger.warning("Returning unapproved answer after %d attempts.", self.max_retries + 1)
        return GroundedAnswer(
            answer=answer,
            citations=citations,
            approved=False,
            refused=False,
            attempts=self.max_retries + 1,
            critique=report,
            chat_history=self._append_turn(history, question, answer),
        )

    @staticmethod
    def _append_turn(history: List[ChatMessage], question: str, answer: str) -> List[ChatMessage]:
        """Return history extended with this turn.

        Uses LlamaIndex `ChatMessage` so the same WorkspaceChatStore can hold
        history for both this path and the default LlamaIndex chat path — a
        workspace can switch between them without its memory becoming unreadable.
        """
        return history + [
            ChatMessage(role="user", content=question),
            ChatMessage(role="assistant", content=answer),
        ]
