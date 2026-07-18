"""Critic Agent for performing hierarchical audits on generated answers."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from paperpilot.agent.formatting import clean_json_markdown, format_chunks_as_context
from paperpilot.core.models import TextChunk

logger = logging.getLogger(__name__)


class CritiqueReport(BaseModel):
    """The structured report of the hierarchical critique audit."""

    grounding_passed: bool = Field(description="True if all claims are strictly backed by the context, False if there are hallucinations or outside facts.")
    grounding_feedback: str = Field(description="Reasoning/feedback for the grounding check.")
    relevance_passed: bool = Field(description="True if the answer directly and fully addresses the user's question.")
    relevance_feedback: str = Field(description="Reasoning/feedback for the relevance check.")
    style_passed: bool = Field(description="True if the answer matches the requested difficulty and includes page citations when appropriate.")
    style_feedback: str = Field(description="Reasoning/feedback for the style and format check.")
    approved: bool = Field(description="True only if ALL checks (grounding, relevance, style) pass.")
    feedback: str = Field(description="Overall feedback summary. Must start with 'APPROVED' if approved, or 'REJECTED: <details>' if rejected.")


CRITIC_SYSTEM_PROMPT = (
    "You are an AI research critic. Your job is to perform a hierarchical audit of a generated answer "
    "against the provided Source Context and User Question.\n\n"
    "You must perform three sequential checks:\n"
    "1. Grounding Check: Verify if all facts and claims in the answer are strictly supported by the "
    "Source Context. If there are any unsupported assertions or outside knowledge, this check FAILS.\n"
    "2. Relevance Check: Verify if the answer directly and fully addresses the User Question. If it is "
    "evasive or incomplete, this check FAILS.\n"
    "3. Style/Structure Check: Verify if the explanation matches the target explanation difficulty "
    "('{difficulty}') and includes page citations (e.g. [Page X]) when page numbers are present in the context. "
    "If it fails to meet these guidelines, this check FAILS.\n\n"
    "Provide your audit report strictly as a JSON object matching this schema:\n"
    "{{\n"
    "  \"grounding_passed\": true | false,\n"
    "  \"grounding_feedback\": \"Reason for grounding pass/fail\",\n"
    "  \"relevance_passed\": true | false,\n"
    "  \"relevance_feedback\": \"Reason for relevance pass/fail\",\n"
    "  \"style_passed\": true | false,\n"
    "  \"style_feedback\": \"Reason for style pass/fail\",\n"
    "  \"approved\": true | false,\n"
    "  \"feedback\": \"APPROVED or REJECTED: <detailed reasons>\"\n"
    "}}\n"
    "The overall 'approved' field must be true ONLY if all three checks are true."
)


class CriticAgent:
    """Critic Agent that performs multi-level auditing on generated research tutor answers."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model
        logger.info("CriticAgent initialized.")

    def evaluate_answer(
        self,
        question: str,
        chunks: list[TextChunk],
        answer: str,
        difficulty: str = "graduate/expert",
    ) -> CritiqueReport:
        """Evaluate the answer against context using a hierarchical critique audit."""
        if not chunks:
            logger.warning("CriticAgent: No context chunks provided. Automatically rejecting.")
            return CritiqueReport(
                grounding_passed=False,
                grounding_feedback="No context available to evaluate.",
                relevance_passed=False,
                relevance_feedback="Cannot address question without context.",
                style_passed=False,
                style_feedback="Cannot evaluate style without context.",
                approved=False,
                feedback="REJECTED: No context available.",
            )

        # Format context
        context_str = format_chunks_as_context(chunks)

        system_text = CRITIC_SYSTEM_PROMPT.format(difficulty=difficulty)

        prompt = (
            f"Source Context:\n{context_str}\n\n"
            f"User Question: {question}\n\n"
            f"Generated Answer: {answer}"
        )

        messages = [
            SystemMessage(content=system_text),
            HumanMessage(content=prompt),
        ]

        logger.info("CriticAgent evaluating answer...")
        response = self.chat_model.invoke(messages)
        content = str(response.content).strip()

        cleaned_content = clean_json_markdown(content)

        try:
            report = CritiqueReport.model_validate_json(cleaned_content)
            logger.info("CriticAgent audit finished. Approved: %s", report.approved)
            return report
        except Exception as e:
            logger.error("CriticAgent failed to parse critique report: %s. Raw content: %s", e, content)

            # Simple text parsing fallback if LLM returned plain text instead of JSON
            approved = "APPROVED" in content.upper() and not "REJECTED" in content.upper()
            feedback = "APPROVED" if approved else f"REJECTED: {content}"
            return CritiqueReport(
                grounding_passed=approved,
                grounding_feedback=content,
                relevance_passed=approved,
                relevance_feedback=content,
                style_passed=approved,
                style_feedback=content,
                approved=approved,
                feedback=feedback,
            )
