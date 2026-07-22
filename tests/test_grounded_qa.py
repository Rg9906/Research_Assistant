"""
Unit tests for the grounded QA service (retrieve -> tutor -> critic -> retry).

Fully offline: the session manager is replaced by a stub returning canned
LlamaIndex nodes, and both agents run on StubChatModel from test_tutor.py
(reused per CLAUDE.md §10) so no network or API key is involved.
"""

from uuid import uuid4

import pytest
from llama_index.core.llms import ChatMessage
from llama_index.core.schema import NodeWithScore, TextNode

from paperpilot.agent.critic import CriticAgent
from paperpilot.agent.tutor import TutorAgent
from paperpilot.core.models import PaperMetadata
from paperpilot.services.grounded_qa import GroundedQAService, nodes_to_chunks
from paperpilot.services.paper_chat.session import extract_page_number

from tests.test_tutor import StubChatModel


PAPER_ID = uuid4()

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
  "approved": false, "feedback": "REJECTED: unsupported claim about scaling"
}"""


class ScriptedChatModel(StubChatModel):
    """StubChatModel that returns a different canned reply per invocation."""

    responses: list[str] = []
    call_count: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        index = min(self.call_count, len(self.responses) - 1)
        self.response_text = self.responses[index]
        self.call_count += 1
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class StubSessionManager:
    """Stands in for PaperSessionManager, returning fixed retrieval results."""

    def __init__(self, nodes):
        self.nodes = nodes
        self.queries: list[str] = []
        self.calls: list[dict] = []

    def retrieve_across_papers(
        self, papers, query, similarity_top_k=None, apply_postprocessors=True,
        include_lead_chunks=None,
    ):
        self.queries.append(query)
        self.calls.append(
            {"query": query, "top_k": similarity_top_k, "filtered": apply_postprocessors}
        )
        return self.nodes


def make_node(text: str, page: str = "3", score: float = 0.9) -> NodeWithScore:
    node = TextNode(
        text=text,
        metadata={
            "paper_id": str(PAPER_ID),
            "page_label": page,
            "publication_year": 2017,  # int on purpose: TextChunk.metadata is dict[str, str]
            "file_name": "attention.pdf",
        },
    )
    return NodeWithScore(node=node, score=score)


def make_service(nodes, tutor_responses, critic_responses, max_retries=2):
    tutor = TutorAgent(chat_model=ScriptedChatModel(responses=tutor_responses, call_count=0))
    critic = CriticAgent(chat_model=ScriptedChatModel(responses=critic_responses, call_count=0))
    manager = StubSessionManager(nodes)
    service = GroundedQAService(
        session_manager=manager, tutor=tutor, critic=critic, max_retries=max_retries
    )
    return service, manager


PAPERS = [PaperMetadata(paper_id=PAPER_ID, title="Attention Is All You Need")]


class TestNodesToChunks:
    """The single translation point between LlamaIndex and core/models.py."""

    def test_converts_nodes_and_stringifies_metadata(self):
        chunks = nodes_to_chunks([make_node("Self-attention scales quadratically.")])
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.paper_id == PAPER_ID
        assert chunk.start_page == 3
        assert chunk.char_count == len("Self-attention scales quadratically.")
        # int metadata must be coerced, not passed through (see CLAUDE.md §7)
        assert chunk.metadata["publication_year"] == "2017"

    def test_node_without_paper_id_is_kept_not_dropped(self):
        node = NodeWithScore(node=TextNode(text="orphan chunk", metadata={}), score=0.5)
        chunks = nodes_to_chunks([node])
        assert len(chunks) == 1
        assert chunks[0].text == "orphan chunk"


class TestPageExtraction:
    """Readers disagree on where the page number lives (see extract_page_number)."""

    def test_page_label_is_preferred(self):
        assert extract_page_number({"page_label": "7", "source": "3"}) == "7"

    def test_pymupdf_source_is_used_as_a_page_number(self):
        # PyMuPDFReader is the primary reader and puts the page in `source`;
        # missing this rendered every citation as "Page N/A".
        assert extract_page_number({"source": "5"}) == "5"

    def test_non_numeric_source_is_not_mistaken_for_a_page(self):
        assert extract_page_number({"source": "data/papers/x.pdf"}) is None

    def test_missing_page_returns_none(self):
        assert extract_page_number({"file_name": "x.pdf"}) is None

    def test_chunk_gets_page_from_pymupdf_source(self):
        node = NodeWithScore(
            node=TextNode(text="t", metadata={"paper_id": str(PAPER_ID), "source": "9"}),
            score=0.8,
        )
        assert nodes_to_chunks([node])[0].start_page == 9


class TestGroundedAnswer:
    """The approve / retry / refuse contract."""

    def test_approved_answer_returns_citations_and_verdict(self):
        service, _ = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["The Transformer uses multi-head attention [Page 3]."],
            critic_responses=[APPROVED_JSON],
        )
        result = service.answer(PAPERS, "What architecture is used?")

        assert result.approved is True
        assert result.refused is False
        assert result.attempts == 1
        assert len(result.citations) == 1
        assert result.citations[0]["page_number"] == "3"

    def test_rejected_answer_is_retried_then_approved(self):
        service, _ = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["It scales linearly.", "It uses multi-head attention [Page 3]."],
            critic_responses=[REJECTED_JSON, APPROVED_JSON],
        )
        result = service.answer(PAPERS, "How does it scale?")

        assert result.attempts == 2
        assert result.approved is True
        assert result.answer == "It uses multi-head attention [Page 3]."

    def test_exhausted_retries_return_flagged_answer_not_an_error(self):
        service, _ = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["Wrong answer."],
            critic_responses=[REJECTED_JSON],
            max_retries=1,
        )
        result = service.answer(PAPERS, "How does it scale?")

        # A flagged answer plus its critique is more useful than a 500.
        assert result.approved is False
        assert result.refused is False
        assert result.attempts == 2
        assert result.critique is not None
        assert "REJECTED" in result.critique.feedback

    def test_empty_retrieval_refuses_without_calling_the_llm(self):
        service, _ = make_service([], tutor_responses=["should not be used"], critic_responses=[APPROVED_JSON])
        result = service.answer(PAPERS, "What is the learning rate?")

        assert result.refused is True
        assert result.approved is False
        assert result.citations == []
        assert result.answer == service.tutor.refusal_response
        assert service.tutor.chat_model.call_count == 0

    def test_tutor_refusal_short_circuits_the_critic(self):
        refusal = "I cannot find the answer in the provided text."
        service, _ = make_service(
            [make_node("Unrelated text about gradient descent.")],
            tutor_responses=[refusal],
            critic_responses=[APPROVED_JSON],
        )
        result = service.answer(PAPERS, "What is the batch size?")

        assert result.refused is True
        assert result.attempts == 1
        assert service.critic.chat_model.call_count == 0

    def test_critic_failure_returns_the_answer_unverified(self):
        """A throttled reviewer must not discard an answer the tutor produced."""
        service, _ = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["It uses multi-head attention [Page 3]."],
            critic_responses=["unused"],
        )

        def boom(*args, **kwargs):
            raise RuntimeError("429 tokens per minute")

        service.critic.evaluate_answer = boom
        result = service.answer(PAPERS, "How does it work?")

        assert result.answer == "It uses multi-head attention [Page 3]."
        assert result.approved is False
        assert result.refused is False
        assert result.citations, "evidence must still travel with the answer"
        assert "audit could not be completed" in result.critique.feedback

    def test_critique_can_be_disabled_to_halve_token_use(self):
        service, _ = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["It uses multi-head attention [Page 3]."],
            critic_responses=[APPROVED_JSON],
        )
        service.critique_enabled = False
        result = service.answer(PAPERS, "How does it work?")

        assert result.answer == "It uses multi-head attention [Page 3]."
        assert result.attempts == 1
        assert service.critic.chat_model.call_count == 0, "no audit call may be made"

    def test_answer_requires_at_least_one_paper(self):
        service, _ = make_service([make_node("text")], ["a"], [APPROVED_JSON])
        with pytest.raises(ValueError, match="at least one paper"):
            service.answer([], "question")


class TestConversationHandling:
    """History is condensed for retrieval and extended for the caller."""

    def test_followup_is_condensed_before_retrieval(self):
        service, manager = make_service(
            [make_node("The Transformer uses multi-head attention.")],
            tutor_responses=["Standalone: what is multi-head attention?", "It splits attention into heads."],
            critic_responses=[APPROVED_JSON],
        )
        history = [
            ChatMessage(role="user", content="What architecture does the paper propose?"),
            ChatMessage(role="assistant", content="The Transformer."),
        ]
        service.answer(PAPERS, "Why does that matter?", chat_history=history)

        # The first tutor-model call is the condense step, whose output becomes
        # the retrieval query rather than the raw pronoun-laden follow-up.
        assert manager.queries == ["Standalone: what is multi-head attention?"]

    def test_no_history_skips_condensing(self):
        service, manager = make_service(
            [make_node("text")], ["An answer."], [APPROVED_JSON]
        )
        service.answer(PAPERS, "What is attention?")
        assert manager.queries == ["What is attention?"]

    def test_returned_history_includes_this_turn(self):
        service, _ = make_service([make_node("text")], ["An answer."], [APPROVED_JSON])
        result = service.answer(PAPERS, "What is attention?")

        assert [m.role.value for m in result.chat_history] == ["user", "assistant"]
        assert result.chat_history[-1].content == "An answer."
