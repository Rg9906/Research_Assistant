"""Unit tests for the Planner Agent."""

from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage

from paperpilot.agent.planner import PlannerAgent, ResearchPlan, PlanStep
from tests.test_tutor import StubChatModel


def test_planner_generates_plan_successfully():
    """PlannerAgent should generate a multi-step ResearchPlan from a valid JSON response."""
    response_json = """
    {
      "difficulty": "undergraduate",
      "steps": [
        {
          "step_index": 0,
          "description": "Search for DPO papers",
          "node": "search",
          "query": "Direct Preference Optimization"
        },
        {
          "step_index": 1,
          "description": "Explain how DPO differs from RLHF",
          "node": "tutor",
          "query": "What are the main differences between DPO and RLHF?"
        }
      ]
    }
    """
    model = StubChatModel(response_text=response_json)
    agent = PlannerAgent(chat_model=model)

    plan = agent.generate_plan("Find papers on DPO and compare with RLHF")

    assert isinstance(plan, ResearchPlan)
    assert plan.difficulty == "undergraduate"
    assert len(plan.steps) == 2
    assert plan.steps[0].node == "search"
    assert plan.steps[0].query == "Direct Preference Optimization"
    assert plan.steps[1].node == "tutor"


def test_planner_handles_markdown_json_fences():
    """PlannerAgent should strip markdown code fences before parsing JSON."""
    response_json = """```json
    {
      "difficulty": "graduate/expert",
      "steps": [
        {
          "step_index": 0,
          "description": "Explain transformers",
          "node": "tutor",
          "query": "Explain transformers"
        }
      ]
    }
    ```"""
    model = StubChatModel(response_text=response_json)
    agent = PlannerAgent(chat_model=model)

    plan = agent.generate_plan("Explain transformers")

    assert plan.difficulty == "graduate/expert"
    assert len(plan.steps) == 1
    assert plan.steps[0].node == "tutor"


def test_planner_fallback_on_json_error():
    """PlannerAgent should fall back to a reasonable single-step plan if LLM output is malformed."""
    model = StubChatModel(response_text="Not JSON at all")
    agent = PlannerAgent(chat_model=model)

    # 1. Fallback for tutor
    plan = agent.generate_plan("Explain attention mechanism")
    assert plan.difficulty == "graduate/expert"
    assert len(plan.steps) == 1
    assert plan.steps[0].node == "tutor"
    assert plan.steps[0].query == "Explain attention mechanism"

    # 2. Fallback for search
    plan_search = agent.generate_plan("Find papers about self-attention")
    assert plan_search.steps[0].node == "search"
    assert plan_search.steps[0].query == "Find papers about self-attention"
