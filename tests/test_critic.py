"""Unit tests for the Critic Agent."""

from uuid import uuid4

from paperpilot.agent.critic import CriticAgent, CritiqueReport
from paperpilot.core.models import TextChunk
from tests.test_tutor import StubChatModel


def test_critic_evaluates_successfully():
    """CriticAgent should return a CritiqueReport indicating approval when LLM JSON report passes."""
    report_json = """
    {
      "grounding_passed": true,
      "grounding_feedback": "Fully supported",
      "relevance_passed": true,
      "relevance_feedback": "Directly answers the query",
      "style_passed": true,
      "style_feedback": "Cites pages correctly",
      "approved": true,
      "feedback": "APPROVED"
    }
    """
    model = StubChatModel(response_text=report_json)
    agent = CriticAgent(chat_model=model)

    chunks = [TextChunk(paper_id=uuid4(), chunk_index=0, text="Self-attention works.", char_count=21)]
    report = agent.evaluate_answer("How does attention work?", chunks, "Self-attention works.")

    assert isinstance(report, CritiqueReport)
    assert report.approved is True
    assert report.grounding_passed is True
    assert report.feedback == "APPROVED"


def test_critic_rejects_hallucinations():
    """CriticAgent should return approved=False if the LLM JSON report shows grounding failed."""
    report_json = """
    {
      "grounding_passed": false,
      "grounding_feedback": "Unsupported claims about pizza",
      "relevance_passed": true,
      "relevance_feedback": "Addresses prompt",
      "style_passed": true,
      "style_feedback": "Good difficulty",
      "approved": false,
      "feedback": "REJECTED: Hallucination detected"
    }
    """
    model = StubChatModel(response_text=report_json)
    agent = CriticAgent(chat_model=model)

    chunks = [TextChunk(paper_id=uuid4(), chunk_index=0, text="Self-attention works.", char_count=21)]
    report = agent.evaluate_answer("How does attention work?", chunks, "Attention works by baking pizza.")

    assert report.approved is False
    assert report.grounding_passed is False
    assert "REJECTED" in report.feedback


def test_critic_automatically_rejects_empty_context():
    """CriticAgent should reject automatically without calling LLM if context chunks are empty."""
    model = StubChatModel()
    agent = CriticAgent(chat_model=model)

    report = agent.evaluate_answer("Any question?", chunks=[], answer="Some answer.")

    assert report.approved is False
    assert len(model.captured_messages) == 0


def test_critic_fallback_on_json_error():
    """CriticAgent should fall back to parsing plain text if the LLM output is not valid JSON."""
    model = StubChatModel(response_text="APPROVED - everything is grounded.")
    agent = CriticAgent(chat_model=model)

    chunks = [TextChunk(paper_id=uuid4(), chunk_index=0, text="Self-attention works.", char_count=21)]
    report = agent.evaluate_answer("test?", chunks, "Self-attention works.")

    assert report.approved is True
    assert report.feedback == "APPROVED"
