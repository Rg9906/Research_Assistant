"""Production unit tests for PaperSession & PaperSessionManager."""

import pytest
from uuid import uuid4
from pathlib import Path

from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from paperpilot.core.models import PaperMetadata
from paperpilot.services.paper_chat.session import (
    MultiPaperRetriever,
    PaperSessionManager,
    compute_pdf_sha256,
)
from paperpilot.services.paper_chat.exceptions import PDFDownloadError, PaperChatException


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
