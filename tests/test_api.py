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
    get_optional_grounded_qa_service,
    get_paper_session_manager,
    get_summarizer_service,
    get_workspace_chat_store,
)
from paperpilot.core.models import PaperMetadata  # noqa: E402
from paperpilot.services.grounded_qa import GroundedAnswer  # noqa: E402

WORKSPACE_ID = uuid4()
PAPER = PaperMetadata(paper_id=uuid4(), title="Attention Is All You Need", authors=["Vaswani"])

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
        defaults = dict(
            answer="The Transformer uses multi-head attention [Page 3].",
            citations=[CITATION],
            approved=True,
            refused=False,
            attempts=1,
        )
        defaults.update(self.answer_kwargs)
        return GroundedAnswer(**defaults)


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


@pytest.fixture
def client():
    """A TestClient with all heavyweight dependencies stubbed out."""
    app.dependency_overrides[get_db_manager] = lambda: StubDB()
    app.dependency_overrides[get_optional_grounded_qa_service] = lambda: StubQA()
    app.dependency_overrides[get_summarizer_service] = lambda: StubSummarizer()
    app.dependency_overrides[get_workspace_chat_store] = lambda: WorkspaceChatStore()
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
