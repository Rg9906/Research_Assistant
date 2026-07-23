"""
Endpoint tests for the FastAPI layer.

Fully offline: every expensive collaborator (workspace DB, grounded-QA service,
summarizer, session manager) is replaced through FastAPI's dependency_overrides,
so these exercise real request/response wiring — routing, status codes, and the
response contract the frontend consumes — without a database, an LLM, or a PDF.
"""

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.api import app  # noqa: E402
from app.utils import (  # noqa: E402
    WorkspaceChatStore,
    get_db_manager,
    get_optional_comparison_service,
    get_optional_grounded_qa_service,
    get_paper_session_manager,
    get_summarizer_service,
    get_workspace_chat_store,
)
from paperpilot.core.models import PaperMetadata  # noqa: E402
from paperpilot.services.comparison import ComparisonAnswer  # noqa: E402
from paperpilot.services.grounded_qa import GroundedAnswer, append_chat_turn  # noqa: E402

WORKSPACE_ID = uuid4()
PAPER = PaperMetadata(paper_id=uuid4(), title="Attention Is All You Need", authors=["Vaswani"])
PAPER_2 = PaperMetadata(paper_id=uuid4(), title="BERT", authors=["Devlin"])

CITATION = {
    "rank": 1,
    "node_id": "n1",
    "score": 0.91,
    "is_lead": False,
    "text": "The Transformer uses multi-head attention.",
    "page_number": "3",
    "filename": "attention.pdf",
    "paper_id": str(PAPER.paper_id),
    "metadata": {"publication_year": "2017"},
}

LEAD_CITATION = {
    "rank": 2,
    "node_id": "n2",
    "score": None,  # a lead chunk carries no similarity score
    "is_lead": True,
    "text": "Abstract: we propose the Transformer.",
    "page_number": "1",
    "filename": "attention.pdf",
    "paper_id": str(PAPER.paper_id),
    "metadata": {},
}


class StubDB:
    def __init__(self, papers=None, paper=None):
        self.papers = papers if papers is not None else [PAPER]
        self.paper = paper

    def get_workspace_papers(self, workspace_id):
        return self.papers

    def get_paper_by_id(self, paper_id):
        return self.paper


class StubQA:
    def __init__(self, **answer_kwargs):
        self.answer_kwargs = answer_kwargs
        self.calls = []

    def answer(self, papers, question, chat_history=None, difficulty="graduate/expert"):
        self.calls.append({"question": question, "difficulty": difficulty})
        answer_text = self.answer_kwargs.get("answer", "The Transformer uses multi-head attention [Page 3].")
        defaults = dict(
            answer=answer_text,
            citations=[CITATION],
            approved=True,
            refused=False,
            attempts=1,
            # Mirrors GroundedQAService.answer(), which always appends this
            # turn to whatever history it was given — a stub that always
            # returned [] made it impossible to test history round-tripping
            # through the endpoint (see append_chat_turn in grounded_qa.py).
            chat_history=append_chat_turn(chat_history or [], question, answer_text),
        )
        defaults.update(self.answer_kwargs)
        return GroundedAnswer(**defaults)


class StubChatDB:
    """In-memory stand-in for WorkspaceManager's chat_messages table.

    Keeps TestChatEndpoint/TestChatHistoryEndpoints/TestCompareEndpoint fully
    offline (no SQLite file needed) while still exercising WorkspaceChatStore's
    real get/set/clear write-through logic.
    """

    def __init__(self):
        self._rows: dict[str, list[dict]] = {}

    def get_chat_messages(self, workspace_id):
        return list(self._rows.get(str(workspace_id), []))

    def replace_chat_messages(self, workspace_id, messages):
        self._rows[str(workspace_id)] = [{"role": r, "content": c} for r, c in messages]

    def clear_chat_messages(self, workspace_id):
        self._rows.pop(str(workspace_id), None)


class StubComparison:
    def __init__(self, **answer_kwargs):
        self.answer_kwargs = answer_kwargs
        self.calls = []

    def compare(self, papers, axis, chat_history=None, difficulty="graduate/expert"):
        self.calls.append({"papers": [p.paper_id for p in papers], "axis": axis, "difficulty": difficulty})
        defaults = dict(
            sections=[{"paper_id": str(PAPER.paper_id), "title": PAPER.title, "summary": "Uses SGD."}],
            synthesis="They differ in optimizer.",
            citations=[CITATION],
            approved=True,
            refused=False,
            attempts=1,
        )
        defaults.update(self.answer_kwargs)
        return ComparisonAnswer(**defaults)


class StubSummarizer:
    def __init__(self, summary="A five sentence summary.", from_cache=False, raises=None):
        self.summary = summary
        self.from_cache = from_cache
        self.raises = raises
        self.calls = []

    def summarize(self, paper, level_id, regenerate=False):
        if self.raises:
            raise self.raises
        self.calls.append({"level_id": level_id, "regenerate": regenerate})
        return self.summary, self.from_cache

    def prefetch(self, paper):
        self.calls.append({"prefetch": True})
        return {"cached": ["quick"], "pending": ["beginner", "technical"]}

    def status(self, paper):
        return {"cached": ["quick"], "pending": ["beginner"]}


@pytest.fixture
def client():
    """A TestClient with all heavyweight dependencies stubbed out."""
    app.dependency_overrides[get_db_manager] = lambda: StubDB()
    app.dependency_overrides[get_optional_grounded_qa_service] = lambda: StubQA()
    app.dependency_overrides[get_optional_comparison_service] = lambda: StubComparison()
    app.dependency_overrides[get_summarizer_service] = lambda: StubSummarizer()
    # A single instance, not `lambda: WorkspaceChatStore(...)`: FastAPI calls a
    # dependency_overrides lambda fresh on every request, so a per-call lambda
    # would give a POST and a later GET two unrelated stores/DBs and history
    # would never appear to round-trip. Production relies on get_workspace_chat_store
    # being @lru_cache'd for the same reason.
    chat_store = WorkspaceChatStore(db=StubChatDB())
    app.dependency_overrides[get_workspace_chat_store] = lambda: chat_store
    app.dependency_overrides[get_paper_session_manager] = lambda: None
    # Deliberately NOT used as a context manager: entering one runs the app's
    # lifespan, which warms the real embedding models (a multi-minute download
    # on a cold machine). These tests exercise routing and contracts, not
    # startup, so the lifespan is skipped to keep the suite fast and offline.
    yield TestClient(app)
    app.dependency_overrides.clear()


def override(dependency, value):
    app.dependency_overrides[dependency] = lambda: value


class TestChatEndpoint:
    def test_returns_answer_with_citations_and_verdict(self, client):
        res = client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "What architecture?"})

        assert res.status_code == 200
        body = res.json()
        assert body["answer"].startswith("The Transformer")
        assert body["approved"] is True
        assert body["refused"] is False
        assert len(body["citations"]) == 1
        assert body["citations"][0]["page_number"] == "3"

    def test_lead_chunk_citation_has_null_score_and_is_flagged(self, client):
        override(get_optional_grounded_qa_service, StubQA(citations=[CITATION, LEAD_CITATION]))
        body = client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "About?"}).json()

        cites = {c["rank"]: c for c in body["citations"]}
        # A similarity hit keeps its score; a lead chunk is null + flagged, so
        # the UI can label it "Intro" instead of rendering a misleading 0.00.
        assert cites[1]["score"] == pytest.approx(0.91)
        assert cites[1]["is_lead"] is False
        assert cites[2]["score"] is None
        assert cites[2]["is_lead"] is True

    def test_difficulty_is_forwarded_to_the_service(self, client):
        qa = StubQA()
        override(get_optional_grounded_qa_service, qa)

        client.post(
            f"/api/workspaces/{WORKSPACE_ID}/chat",
            json={"query": "Explain simply", "difficulty": "beginner"},
        )
        assert qa.calls[0]["difficulty"] == "beginner"

    def test_difficulty_defaults_when_omitted(self, client):
        qa = StubQA()
        override(get_optional_grounded_qa_service, qa)

        client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "Explain"})
        assert qa.calls[0]["difficulty"] == "graduate/expert"

    def test_flagged_answer_is_surfaced_not_hidden(self, client):
        override(
            get_optional_grounded_qa_service,
            StubQA(approved=False, attempts=3),
        )
        body = client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "q"}).json()

        # The UI relies on this flag to warn the user rather than presenting an
        # unreviewed answer as verified.
        assert body["approved"] is False
        assert body["attempts"] == 3

    def test_empty_workspace_returns_400(self, client):
        override(get_db_manager, StubDB(papers=[]))
        res = client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "q"})
        assert res.status_code == 400

    def test_paper_ids_narrows_scope_but_history_still_threads(self, client):
        override(get_db_manager, StubDB(papers=[PAPER, PAPER_2]))
        qa = StubQA()
        override(get_optional_grounded_qa_service, qa)

        client.post(
            f"/api/workspaces/{WORKSPACE_ID}/chat",
            json={"query": "q1", "paper_ids": [str(PAPER.paper_id)]},
        )
        client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "q2"})

        # First call was scoped to one paper; the second (unscoped) call still
        # sees the first call's turn in history, proving both calls threaded
        # through the same store rather than paper_ids resetting memory.
        assert qa.calls[0]["question"] == "q1"
        assert qa.calls[1]["question"] == "q2"

    def test_unknown_paper_ids_returns_400(self, client):
        override(get_db_manager, StubDB(papers=[PAPER]))
        res = client.post(
            f"/api/workspaces/{WORKSPACE_ID}/chat",
            json={"query": "q", "paper_ids": [str(uuid4())]},
        )
        assert res.status_code == 400


class TestChatHistoryEndpoints:
    def test_history_reflects_a_prior_chat_turn(self, client):
        client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "What architecture?"})

        body = client.get(f"/api/workspaces/{WORKSPACE_ID}/chat/history").json()

        roles = [m["role"] for m in body["messages"]]
        assert roles == ["user", "assistant"]
        assert body["messages"][0]["content"] == "What architecture?"

    def test_history_is_empty_for_a_fresh_workspace(self, client):
        body = client.get(f"/api/workspaces/{uuid4()}/chat/history").json()
        assert body["messages"] == []

    def test_delete_clears_history(self, client):
        client.post(f"/api/workspaces/{WORKSPACE_ID}/chat", json={"query": "q"})

        res = client.delete(f"/api/workspaces/{WORKSPACE_ID}/chat/history")
        assert res.status_code == 200

        body = client.get(f"/api/workspaces/{WORKSPACE_ID}/chat/history").json()
        assert body["messages"] == []


class TestCompareEndpoint:
    def test_happy_path_returns_synthesis_and_sections(self, client):
        override(get_db_manager, StubDB(papers=[PAPER, PAPER_2]))
        res = client.post(f"/api/workspaces/{WORKSPACE_ID}/compare", json={"axis": "optimizer"})

        assert res.status_code == 200
        body = res.json()
        assert body["synthesis"] == "They differ in optimizer."
        assert len(body["sections"]) == 1
        assert body["approved"] is True

    def test_fewer_than_two_papers_returns_400(self, client):
        override(get_db_manager, StubDB(papers=[PAPER]))
        res = client.post(f"/api/workspaces/{WORKSPACE_ID}/compare", json={"axis": "optimizer"})
        assert res.status_code == 400

    def test_paper_ids_filters_the_comparison_set(self, client):
        override(get_db_manager, StubDB(papers=[PAPER, PAPER_2]))
        comparison = StubComparison()
        override(get_optional_comparison_service, comparison)

        client.post(
            f"/api/workspaces/{WORKSPACE_ID}/compare",
            json={"axis": "optimizer", "paper_ids": [str(PAPER.paper_id), str(PAPER_2.paper_id)]},
        )
        assert set(comparison.calls[0]["papers"]) == {PAPER.paper_id, PAPER_2.paper_id}

    def test_service_unavailable_returns_503(self, client):
        override(get_db_manager, StubDB(papers=[PAPER, PAPER_2]))
        override(get_optional_comparison_service, None)

        res = client.post(f"/api/workspaces/{WORKSPACE_ID}/compare", json={"axis": "optimizer"})
        assert res.status_code == 503

    def test_flagged_comparison_is_surfaced(self, client):
        override(get_db_manager, StubDB(papers=[PAPER, PAPER_2]))
        override(get_optional_comparison_service, StubComparison(approved=False, attempts=3))

        body = client.post(f"/api/workspaces/{WORKSPACE_ID}/compare", json={"axis": "optimizer"}).json()
        assert body["approved"] is False
        assert body["attempts"] == 3


class TestSummaryEndpoints:
    def test_summary_levels_are_listed(self, client):
        body = client.get("/api/summary-levels").json()
        ids = {level["id"] for level in body["levels"]}

        assert {"quick", "beginner", "technical", "limitations"} <= ids
        # The frontend renders label + difficulty straight from this payload.
        assert all({"id", "label", "difficulty"} <= set(level) for level in body["levels"])

    def test_summary_is_generated_for_a_known_paper(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        res = client.post(f"/api/papers/{PAPER.paper_id}/summary/quick")

        assert res.status_code == 200
        body = res.json()
        assert body["summary"] == "A five sentence summary."
        assert body["from_cache"] is False
        assert body["level_id"] == "quick"

    def test_cache_hit_is_reported(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        override(get_summarizer_service, StubSummarizer(from_cache=True))

        body = client.post(f"/api/papers/{PAPER.paper_id}/summary/quick").json()
        assert body["from_cache"] is True

    def test_regenerate_flag_is_forwarded(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        summarizer = StubSummarizer()
        override(get_summarizer_service, summarizer)

        client.post(f"/api/papers/{PAPER.paper_id}/summary/quick?regenerate=true")
        assert summarizer.calls[0]["regenerate"] is True

    def test_unknown_paper_returns_404(self, client):
        override(get_db_manager, StubDB(paper=None))
        res = client.post(f"/api/papers/{uuid4()}/summary/quick")
        assert res.status_code == 404

    def test_unknown_level_returns_400(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        override(get_summarizer_service, StubSummarizer(raises=KeyError("Unknown summary level")))

        res = client.post(f"/api/papers/{PAPER.paper_id}/summary/not-a-level")
        assert res.status_code == 400


class TestSummaryPrefetchEndpoints:
    def test_prefetch_triggers_background_generation(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        summarizer = StubSummarizer()
        override(get_summarizer_service, summarizer)

        res = client.post(f"/api/papers/{PAPER.paper_id}/summaries/prefetch")
        assert res.status_code == 200
        body = res.json()
        assert body["cached"] == ["quick"]
        assert body["pending"] == ["beginner", "technical"]
        assert {"prefetch": True} in summarizer.calls

    def test_prefetch_unknown_paper_returns_404(self, client):
        override(get_db_manager, StubDB(paper=None))
        res = client.post(f"/api/papers/{uuid4()}/summaries/prefetch")
        assert res.status_code == 404

    def test_status_reports_cached_and_pending(self, client):
        override(get_db_manager, StubDB(paper=PAPER))
        override(get_summarizer_service, StubSummarizer())

        res = client.get(f"/api/papers/{PAPER.paper_id}/summaries")
        assert res.status_code == 200
        body = res.json()
        assert body["cached"] == ["quick"]
        assert body["pending"] == ["beginner"]

    def test_status_unknown_paper_returns_404(self, client):
        override(get_db_manager, StubDB(paper=None))
        res = client.get(f"/api/papers/{uuid4()}/summaries")
        assert res.status_code == 404
