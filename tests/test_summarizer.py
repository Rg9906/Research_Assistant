"""
Unit tests for the multi-level summarizer and its on-disk cache.

Offline: the GroundedQAService is replaced by a stub that records calls, so
these tests cover caching, level definitions, and the no-history guarantee
without any LLM involvement. `tmp_path` isolates the cache directory.
"""

from uuid import uuid4

import pytest

from paperpilot.core.models import PaperMetadata
from paperpilot.services.grounded_qa import GroundedAnswer
from paperpilot.services.summarizer import (
    LEVELS_BY_ID,
    SUMMARY_LEVELS,
    SummarizerService,
)


class StubQAService:
    """Records every answer() call and returns a canned GroundedAnswer."""

    def __init__(self, answer_text="A generated summary.", refused=False):
        self.answer_text = answer_text
        self.refused = refused
        self.calls: list[dict] = []

    def answer(
        self,
        papers,
        question,
        chat_history=None,
        difficulty="graduate/expert",
        retrieval_query=None,
        similarity_top_k=None,
        apply_similarity_cutoff=True,
    ):
        self.calls.append(
            {
                "papers": papers,
                "question": question,
                "history": chat_history,
                "difficulty": difficulty,
                "retrieval_query": retrieval_query,
                "top_k": similarity_top_k,
                "cutoff": apply_similarity_cutoff,
            }
        )
        return GroundedAnswer(
            answer=self.answer_text,
            citations=[],
            approved=not self.refused,
            refused=self.refused,
            attempts=1,
        )


@pytest.fixture
def paper():
    return PaperMetadata(paper_id=uuid4(), title="Attention Is All You Need")


def make_service(tmp_path, **kwargs):
    qa = StubQAService(**kwargs)
    return SummarizerService(qa_service=qa, storage_dir=tmp_path), qa


class TestSummaryLevels:
    """The level catalogue is the backend's contract with every client."""

    def test_vision_levels_are_all_present(self):
        expected = {
            "quick", "beginner", "technical", "contributions", "methodology",
            "results", "limitations", "future_work", "prerequisites", "glossary",
        }
        assert expected <= set(LEVELS_BY_ID)

    def test_ids_are_unique(self):
        ids = [level.id for level in SUMMARY_LEVELS]
        assert len(ids) == len(set(ids))

    def test_beginner_level_requests_beginner_difficulty(self):
        # The difficulty is what the critic audits the answer's style against,
        # so it has to match the level's intent.
        assert LEVELS_BY_ID["beginner"].difficulty == "beginner"
        assert LEVELS_BY_ID["technical"].difficulty == "graduate/expert"


class TestSummarize:
    def test_generates_and_reports_not_cached(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        summary, from_cache = service.summarize(paper, "quick")

        assert summary == "A generated summary."
        assert from_cache is False
        assert len(qa.calls) == 1

    def test_second_call_hits_cache_without_calling_the_llm(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")
        summary, from_cache = service.summarize(paper, "quick")

        assert from_cache is True
        assert summary == "A generated summary."
        assert len(qa.calls) == 1, "cached level must not re-invoke the QA service"

    def test_cache_persists_across_service_instances(self, tmp_path, paper):
        service, _ = make_service(tmp_path)
        service.summarize(paper, "quick")

        # A new process/service should still see the cached summary on disk.
        fresh_service, fresh_qa = make_service(tmp_path)
        summary, from_cache = fresh_service.summarize(paper, "quick")
        assert from_cache is True
        assert summary == "A generated summary."
        assert fresh_qa.calls == []

    def test_regenerate_bypasses_and_overwrites_cache(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")
        qa.answer_text = "A better summary."

        summary, from_cache = service.summarize(paper, "quick", regenerate=True)
        assert from_cache is False
        assert summary == "A better summary."

        # The overwrite must stick.
        cached, from_cache = service.summarize(paper, "quick")
        assert from_cache is True
        assert cached == "A better summary."

    def test_levels_are_cached_independently(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")
        service.summarize(paper, "limitations")

        assert len(qa.calls) == 2
        assert service.get_cached_levels(paper) == ["limitations", "quick"]

    def test_papers_are_cached_independently(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        other = PaperMetadata(paper_id=uuid4(), title="BERT")

        service.summarize(paper, "quick")
        service.summarize(other, "quick")

        assert len(qa.calls) == 2
        assert service.get_cached_levels(other) == ["quick"]

    def test_summaries_are_generated_without_conversation_history(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.summarize(paper, "technical")

        # Passing history would make the same tab render differently depending
        # on what the user had chatted about first.
        assert qa.calls[0]["history"] is None
        assert qa.calls[0]["difficulty"] == "graduate/expert"

    def test_refusal_is_returned_but_not_cached(self, tmp_path, paper):
        service, qa = make_service(tmp_path, answer_text="I cannot find the answer in the provided text.", refused=True)
        summary, from_cache = service.summarize(paper, "results")

        assert from_cache is False
        assert service.get_cached_levels(paper) == []

        # A transient retrieval miss must not become a permanent cached answer.
        service.summarize(paper, "results")
        assert len(qa.calls) == 2

    def test_retrieval_uses_paper_content_not_the_instruction(self, tmp_path, paper):
        """Regression: instruction-shaped prompts retrieved nothing.

        "Summarize this paper in five sentences" resembles no passage in the
        paper, so similarity retrieval scored every chunk below the cutoff and
        every summary level refused. Retrieval must search on the paper's own
        title/abstract, with the cutoff off.
        """
        paper.abstract = "We propose the Transformer, based solely on attention."
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")

        call = qa.calls[0]
        assert paper.title in call["retrieval_query"]
        assert paper.abstract in call["retrieval_query"]
        assert call["cutoff"] is False
        assert call["top_k"] == service.top_k
        # The instruction still drives generation, just not retrieval.
        assert "five" in call["question"]

    def test_retrieval_query_tolerates_a_missing_abstract(self, tmp_path, paper):
        paper.abstract = None
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")
        assert qa.calls[0]["retrieval_query"] == paper.title

    def test_unknown_level_raises(self, tmp_path, paper):
        service, _ = make_service(tmp_path)
        with pytest.raises(KeyError, match="Unknown summary level"):
            service.summarize(paper, "not-a-level")

    def test_corrupt_cache_file_is_ignored(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        cache_path = service._cache_path(paper)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("{ this is not json", encoding="utf-8")

        summary, from_cache = service.summarize(paper, "quick")
        assert from_cache is False
        assert summary == "A generated summary."
