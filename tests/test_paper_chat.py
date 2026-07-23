"""Production unit tests for PaperSession & PaperSessionManager."""

import pytest
from pathlib import Path

from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from paperpilot.core.models import PaperMetadata
from paperpilot.services.paper_chat.session import (
    MultiPaperRetriever,
    PaperSession,
    PaperSessionManager,
    compute_pdf_sha256,
)
from paperpilot.services.paper_chat.exceptions import PDFDownloadError


def test_compute_pdf_sha256(tmp_path: Path):
    dummy_file = tmp_path / "test.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 test content")
    sha = compute_pdf_sha256(dummy_file)
    assert len(sha) == 64
    assert isinstance(sha, str)


def test_session_manager_initialization():
    mgr = PaperSessionManager()
    assert mgr is not None
    assert mgr.base_dir.exists()


def test_session_manager_missing_url():
    mgr = PaperSessionManager()
    meta = PaperMetadata(title="Test Paper", pdf_url="")

    with pytest.raises(PDFDownloadError):
        mgr.get_or_create_session(metadata=meta)


def _node_with_score(score: float, text: str) -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=score)


class _FakeRetriever:
    def __init__(self, nodes: list[NodeWithScore]) -> None:
        self._nodes = nodes

    def retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        return self._nodes


class _FakeIndex:
    def __init__(self, nodes: list[NodeWithScore]) -> None:
        self._nodes = nodes

    def as_retriever(self, similarity_top_k: int = 5) -> _FakeRetriever:
        return _FakeRetriever(self._nodes[:similarity_top_k])


class _FakeSession:
    def __init__(self, nodes: list[NodeWithScore]) -> None:
        self.index = _FakeIndex(nodes)


def test_multi_paper_retriever_merges_and_sorts_by_score():
    """Results from every paper's index should be merged and ranked by score.

    Regression test for the "chat only ever uses papers[0]" bug: this
    verifies the merge logic that lets a multi-paper workspace be grounded
    in whichever paper's chunks are actually most relevant, not just the
    first paper added to the workspace.
    """
    session_a = _FakeSession([_node_with_score(0.9, "a1"), _node_with_score(0.5, "a2")])
    session_b = _FakeSession([_node_with_score(0.8, "b1"), _node_with_score(0.3, "b2")])

    retriever = MultiPaperRetriever([session_a, session_b], similarity_top_k=3)
    results = retriever._retrieve(QueryBundle(query_str="test"))

    assert [n.score for n in results] == [0.9, 0.8, 0.5]
    assert [n.node.get_content() for n in results] == ["a1", "b1", "a2"]


def test_multi_paper_retriever_respects_top_k():
    session_a = _FakeSession([_node_with_score(0.9, "a1")])
    session_b = _FakeSession([_node_with_score(0.8, "b1")])

    retriever = MultiPaperRetriever([session_a, session_b], similarity_top_k=1)
    results = retriever._retrieve(QueryBundle(query_str="test"))

    assert len(results) == 1
    assert results[0].node.get_content() == "a1"


# ---------------------------------------------------------------------------
# Lead-chunk retrieval
#
# Vector search cannot surface a paper's framing for document-level questions
# ("what problem does this paper address?"), because the abstract shares no
# vocabulary with such a question. PaperSession.get_lead_nodes supplies it by
# position instead of by similarity.
# ---------------------------------------------------------------------------


class _FakeDocstore:
    def __init__(self, docs: dict) -> None:
        self.docs = docs


class _IndexWithDocstore(_FakeIndex):
    def __init__(self, nodes: list[NodeWithScore], docs: dict) -> None:
        super().__init__(nodes)
        self.docstore = _FakeDocstore(docs)


def _page_node(node_id: str, page: str, text: str, start: int = 0) -> TextNode:
    return TextNode(id_=node_id, text=text, metadata={"source": page}, start_char_idx=start)


def _session_with_pages(pages: list[tuple[str, str, str]]) -> "PaperSession":
    docs = {nid: _page_node(nid, page, text) for nid, page, text in pages}
    session = PaperSession.__new__(PaperSession)  # bypass __init__ (needs settings/PDF)
    session.index = _IndexWithDocstore([], docs)
    return session


class TestGetLeadNodes:
    def test_returns_earliest_pages_in_order(self):
        session = _session_with_pages([
            ("n3", "7", "mid-document results"),
            ("n1", "1", "title and abstract"),
            ("n2", "2", "introduction"),
        ])

        leads = session.get_lead_nodes(2)
        assert [n.node.get_content() for n in leads] == ["title and abstract", "introduction"]

    def test_lead_nodes_carry_no_score(self):
        """A fabricated score would corrupt merge ranking and the citation list."""
        session = _session_with_pages([("n1", "1", "abstract")])
        assert session.get_lead_nodes(1)[0].score is None

    def test_zero_limit_disables_the_feature(self):
        session = _session_with_pages([("n1", "1", "abstract")])
        assert session.get_lead_nodes(0) == []

    def test_nodes_without_a_page_sort_last(self):
        session = _session_with_pages([
            ("n2", "3", "page three"),
        ])
        session.index.docstore.docs["n1"] = TextNode(id_="n1", text="no page", metadata={})

        leads = session.get_lead_nodes(1)
        assert leads[0].node.get_content() == "page three"
