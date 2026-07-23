"""
Unit tests for the Comparison agent and service.

Fully offline, following the same conventions as test_critic.py and
test_grounded_qa.py: StubChatModel from test_tutor.py for the LLM calls, and a
StubSessionManager returning canned LlamaIndex nodes for retrieval.
"""

from uuid import uuid4

from llama_index.core.schema import NodeWithScore, TextNode

from paperpilot.agent.comparison import ComparisonAgent, ComparisonReport
from paperpilot.agent.critic import CriticAgent
from paperpilot.core.models import PaperMetadata, TextChunk
from paperpilot.services.comparison import ComparisonService

from tests.test_tutor import StubChatModel
from tests.test_grounded_qa import ScriptedChatModel

PAPER_A_ID = uuid4()
PAPER_B_ID = uuid4()

APPROVED_JSON = """{
  "grounding_passed": true, "grounding_feedback": "ok",
  "relevance_passed": true, "relevance_feedback": "ok",
  "style_passed": true, "style_feedback": "ok",
  "approved": true, "feedback": "APPROVED"
}"""

REJECTED_JSON = """{
  "grounding_passed": false, "grounding_feedback": "unsupported claim",
  "relevance_passed": true, "relevance_feedback": "ok",
  "style_passed": true, "style_feedback": "ok",
  "approved": false, "feedback": "REJECTED: unsupported claim"
}"""


def make_report_json(refused: bool = False) -> str:
    if refused:
        return '{"sections": [], "synthesis": "", "refused": true}'
    return (
        '{"sections": ['
        f'{{"paper_id": "{PAPER_A_ID}", "title": "Paper A", "summary": "Uses SGD."}}, '
        f'{{"paper_id": "{PAPER_B_ID}", "title": "Paper B", "summary": "Uses Adam."}}'
        '], "synthesis": "They differ in optimizer.", "refused": false}'
    )


class TestComparisonAgent:
    def test_compares_two_papers(self):
        chunks_a = [TextChunk(paper_id=PAPER_A_ID, chunk_index=0, text="Uses SGD.", char_count=9)]
        chunks_b = [TextChunk(paper_id=PAPER_B_ID, chunk_index=0, text="Uses Adam.", char_count=10)]
        agent = ComparisonAgent(chat_model=StubChatModel(response_text=make_report_json()))

        report = agent.compare(
            "optimizer",
            {str(PAPER_A_ID): ("Paper A", chunks_a), str(PAPER_B_ID): ("Paper B", chunks_b)},
        )

        assert isinstance(report, ComparisonReport)
        assert report.refused is False
        assert len(report.sections) == 2
        assert report.synthesis == "They differ in optimizer."

    def test_refuses_with_fewer_than_two_papers_of_context_and_makes_no_llm_call(self):
        chunks_a = [TextChunk(paper_id=PAPER_A_ID, chunk_index=0, text="Uses SGD.", char_count=9)]
        model = StubChatModel(response_text=make_report_json())
        agent = ComparisonAgent(chat_model=model)

        report = agent.compare(
            "optimizer",
            {str(PAPER_A_ID): ("Paper A", chunks_a), str(PAPER_B_ID): ("Paper B", [])},
        )

        assert report.refused is True
        assert len(model.captured_messages) == 0

    def test_strips_markdown_fences(self):
        fenced = "```json\n" + make_report_json() + "\n```"
        chunks_a = [TextChunk(paper_id=PAPER_A_ID, chunk_index=0, text="Uses SGD.", char_count=9)]
        chunks_b = [TextChunk(paper_id=PAPER_B_ID, chunk_index=0, text="Uses Adam.", char_count=10)]
        agent = ComparisonAgent(chat_model=StubChatModel(response_text=fenced))

        report = agent.compare(
            "optimizer",
            {str(PAPER_A_ID): ("Paper A", chunks_a), str(PAPER_B_ID): ("Paper B", chunks_b)},
        )
        assert report.refused is False
        assert len(report.sections) == 2

    def test_falls_back_to_plain_text_on_malformed_json(self):
        chunks_a = [TextChunk(paper_id=PAPER_A_ID, chunk_index=0, text="Uses SGD.", char_count=9)]
        chunks_b = [TextChunk(paper_id=PAPER_B_ID, chunk_index=0, text="Uses Adam.", char_count=10)]
        agent = ComparisonAgent(chat_model=StubChatModel(response_text="Not JSON at all."))

        report = agent.compare(
            "optimizer",
            {str(PAPER_A_ID): ("Paper A", chunks_a), str(PAPER_B_ID): ("Paper B", chunks_b)},
        )
        assert report.sections == []
        assert report.synthesis == "Not JSON at all."
        assert report.refused is False


def make_node(paper_id, text: str, page: str = "1") -> NodeWithScore:
    node = TextNode(
        text=text,
        metadata={"paper_id": str(paper_id), "page_label": page, "file_name": "paper.pdf"},
    )
    return NodeWithScore(node=node, score=0.8)


class StubSessionManager:
    """Returns one canned node per paper, tagged so the test can tell them apart."""

    def __init__(self):
        self.calls: list[dict] = []

    def retrieve_across_papers(
        self, papers, query, similarity_top_k=None, apply_postprocessors=True, include_lead_chunks=None,
    ):
        self.calls.append({"papers": [p.paper_id for p in papers], "query": query})
        paper = papers[0]
        text = "Uses SGD." if paper.paper_id == PAPER_A_ID else "Uses Adam."
        return [make_node(paper.paper_id, text)]


PAPER_A = PaperMetadata(paper_id=PAPER_A_ID, title="Paper A")
PAPER_B = PaperMetadata(paper_id=PAPER_B_ID, title="Paper B")


def make_service(report_responses, critic_responses, max_retries=2):
    agent = ComparisonAgent(chat_model=ScriptedChatModel(responses=report_responses, call_count=0))
    critic = CriticAgent(chat_model=ScriptedChatModel(responses=critic_responses, call_count=0))
    manager = StubSessionManager()
    service = ComparisonService(
        session_manager=manager, comparison_agent=agent, critic=critic, max_retries=max_retries
    )
    return service, manager


class TestComparisonService:
    def test_refuses_single_paper_without_retrieval(self):
        service, manager = make_service([make_report_json()], [APPROVED_JSON])
        result = service.compare([PAPER_A], "optimizer")

        assert result.refused is True
        assert result.approved is False
        assert manager.calls == []  # no retrieval attempted

    def test_two_paper_happy_path_returns_citations_per_paper(self):
        service, manager = make_service([make_report_json()], [APPROVED_JSON])
        result = service.compare([PAPER_A, PAPER_B], "optimizer")

        assert result.approved is True
        assert result.refused is False
        assert len(result.sections) == 2
        paper_ids_cited = {c["paper_id"] for c in result.citations}
        assert paper_ids_cited == {str(PAPER_A_ID), str(PAPER_B_ID)}
        # Retrieval happened once per paper, not merged.
        assert len(manager.calls) == 2

    def test_returned_history_includes_this_turn(self):
        service, _ = make_service([make_report_json()], [APPROVED_JSON])
        result = service.compare([PAPER_A, PAPER_B], "optimizer")

        roles = [m.role.value for m in result.chat_history]
        assert roles == ["user", "assistant"]

    def test_critic_rejection_retries_then_returns_unapproved(self):
        service, _ = make_service(
            [make_report_json(), make_report_json()],
            [REJECTED_JSON, REJECTED_JSON, REJECTED_JSON],
            max_retries=2,
        )
        result = service.compare([PAPER_A, PAPER_B], "optimizer")

        assert result.approved is False
        assert result.refused is False
        assert result.attempts == 3
        assert result.critique is not None and "REJECTED" in result.critique.feedback

    def test_comparison_agent_refusal_short_circuits_before_critic(self):
        critic = CriticAgent(chat_model=ScriptedChatModel(responses=[APPROVED_JSON], call_count=0))
        agent = ComparisonAgent(chat_model=ScriptedChatModel(responses=[make_report_json(refused=True)], call_count=0))
        manager = StubSessionManager()
        service = ComparisonService(session_manager=manager, comparison_agent=agent, critic=critic)

        result = service.compare([PAPER_A, PAPER_B], "optimizer")
        assert result.refused is True
        assert result.approved is False
