"""Planner Agent for analyzing user queries and formulating multi-step execution plans."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from paperpilot.agent.formatting import clean_json_markdown

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """A single step in the research plan."""

    step_index: int = Field(description="0-indexed position of the step")
    description: str = Field(description="Description of what this step does")
    node: str = Field(description="The graph node to route to: 'search' or 'tutor'")
    query: str = Field(description="The query/question/keywords to run for this step")


class ResearchPlan(BaseModel):
    """The generated multi-step research plan."""

    difficulty: str = Field(
        default="graduate/expert",
        description="Target difficulty level: 'beginner', 'undergraduate', or 'graduate/expert'",
    )
    steps: list[PlanStep] = Field(description="The list of plan steps to execute")


SYSTEM_PROMPT_PLANNER = (
    "You are the routing planner for an AI research assistant.\n"
    "Your job is to analyze the user's request, determine the target explanation difficulty "
    "('beginner', 'undergraduate', or 'graduate/expert'), and break it down into a sequence of steps "
    "to execute.\n\n"
    "Each step must route to one of these nodes:\n"
    "- 'search': If we need to discover papers or search academic literature for keywords.\n"
    "- 'tutor': If we need to retrieve sections from the indexed papers and answer a subquestion.\n\n"
    "Provide the plan strictly as a JSON object matching this schema:\n"
    "{\n"
    "  \"difficulty\": \"beginner | undergraduate | graduate/expert\",\n"
    "  \"steps\": [\n"
    "    {\n"
    "      \"step_index\": 0,\n"
    "      \"description\": \"Description of the step\",\n"
    "      \"node\": \"search | tutor\",\n"
    "      \"query\": \"Search query or subquestion/topic to answer\"\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Example 1 (Simple query): 'Explain self-attention'\n"
    "JSON:\n"
    "{\n"
    "  \"difficulty\": \"graduate/expert\",\n"
    "  \"steps\": [\n"
    "    {\n"
    "      \"step_index\": 0,\n"
    "      \"description\": \"Explain self-attention concept\",\n"
    "      \"node\": \"tutor\",\n"
    "      \"query\": \"Explain self-attention mechanism\"\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Example 2 (Complex query): 'Find papers on DPO and explain key differences from RLHF'\n"
    "JSON:\n"
    "{\n"
    "  \"difficulty\": \"graduate/expert\",\n"
    "  \"steps\": [\n"
    "    {\n"
    "      \"step_index\": 0,\n"
    "      \"description\": \"Search for papers on DPO and RLHF\",\n"
    "      \"node\": \"search\",\n"
    "      \"query\": \"Direct Preference Optimization RLHF\"\n"
    "    },\n"
    "    {\n"
    "      \"step_index\": 1,\n"
    "      \"description\": \"Explain key differences between DPO and RLHF\",\n"
    "      \"node\": \"tutor\",\n"
    "      \"query\": \"What are the key differences between Direct Preference Optimization (DPO) and Reinforcement Learning from Human Feedback (RLHF)?\"\n"
    "    }\n"
    "  ]\n"
    "}"
)


class PlannerAgent:
    """Planner Agent that creates research execution plans from user queries."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model
        logger.info("PlannerAgent initialized.")

    def generate_plan(self, query: str) -> ResearchPlan:
        """Analyze query and return a structured ResearchPlan."""
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_PLANNER),
            HumanMessage(content=query),
        ]

        logger.info("PlannerAgent generating plan for: '%s'", query)
        response = self.chat_model.invoke(messages)
        content = str(response.content).strip()

        # Clean markdown code blocks from output
        cleaned_content = clean_json_markdown(content)

        try:
            plan = ResearchPlan.model_validate_json(cleaned_content)
            logger.info("PlannerAgent successfully generated plan with %d steps.", len(plan.steps))
            return plan
        except Exception as e:
            logger.error("PlannerAgent failed to parse LLM response as ResearchPlan: %s. Raw content: %s", e, content)
            # Fallback plan: default to single-step tutoring or searching
            is_search = any(k in query.lower() for k in ["find", "search", "discover", "papers", "literature"])
            node = "search" if is_search else "tutor"
            return ResearchPlan(
                difficulty="graduate/expert",
                steps=[
                    PlanStep(
                        step_index=0,
                        description=f"Fallback execution step ({node})",
                        node=node,
                        query=query,
                    )
                ],
            )

