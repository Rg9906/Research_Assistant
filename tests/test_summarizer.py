"""
Unit tests for the multi-level summarizer and its on-disk cache.

Offline: the GroundedQAService is replaced by a stub that records calls, so
these tests cover caching, level definitions, and the no-history guarantee
without any LLM involvement. `tmp_path` isolates the cache directory.
"""

import threading
import time
from uuid import uuid4

import pytest

from paperpilot.core.models import PaperMetadata
from paperpilot.services.grounded_qa import GroundedAnswer
from paperpilot.services.summarizer import (
    LEVELS_BY_ID,
    PREFETCH_PRIORITY,
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


def _drain(service, paper, timeout=10.0):
    """Block until the paper's background prefetch queue is empty."""
    end = time.time() + timeout
    while service.pending_levels(paper) and time.time() < end:
        time.sleep(0.02)
    assert not service.pending_levels(paper), "prefetch did not finish in time"


class TestPrefetch:
    def test_prefetch_generates_every_level_once(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.prefetch(paper)
        _drain(service, paper)

        assert set(service.get_cached_levels(paper)) == set(LEVELS_BY_ID)
        assert len(qa.calls) == len(LEVELS_BY_ID)

    def test_prefetch_skips_already_cached_levels(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.summarize(paper, "quick")  # 1 call
        assert len(qa.calls) == 1

        service.prefetch(paper)
        _drain(service, paper)

        # Every level generated exactly once — the pre-cached "quick" is not redone.
        assert len(qa.calls) == len(LEVELS_BY_ID)

    def test_prefetch_is_idempotent(self, tmp_path, paper):
        service, qa = make_service(tmp_path)
        service.prefetch(paper)
        _drain(service, paper)
        calls_after_first = len(qa.calls)

        service.prefetch(paper)  # everything already cached
        _drain(service, paper)
        assert len(qa.calls) == calls_after_first

    def test_prefetch_respects_priority_order(self, tmp_path, paper):
        # One worker makes execution order == submission order == priority order.
        qa = StubQAService()
        service = SummarizerService(qa_service=qa, storage_dir=tmp_path, prefetch_workers=1)
        service.prefetch(paper)
        _drain(service, paper)

        prompt_to_id = {level.prompt: level.id for level in SUMMARY_LEVELS}
        generated_order = [prompt_to_id[c["question"]] for c in qa.calls]
        expected = [lid for lid in PREFETCH_PRIORITY if lid in LEVELS_BY_ID]
        assert generated_order == expected

    def test_status_reports_cached_levels(self, tmp_path, paper):
        service, _ = make_service(tmp_path)
        service.summarize(paper, "quick")
        status = service.status(paper)
        assert status["cached"] == ["quick"]
        assert status["pending"] == []


class TestConcurrencySafety:
    def test_concurrent_same_level_generates_once(self, tmp_path, paper):
        """A background prefetch and an on-demand click for the same level must
        not both pay for the LLM — the second waits and gets the cache."""
        qa = BlockingQAService()
        service = SummarizerService(qa_service=qa, storage_dir=tmp_path)

        results: list[tuple[str, bool]] = []
        lock = threading.Lock()

        def worker():
            r = service.summarize(paper, "quick")
            with lock:
                results.append(r)

        t1 = threading.Thread(target=worker)
        t1.start()
        assert qa.entered.wait(timeout=5), "first generation never started"
        # First thread now holds the level lock inside answer(); start the second.
        t2 = threading.Thread(target=worker)
        t2.start()
        time.sleep(0.1)  # let t2 reach and block on the key lock
        qa.release.set()

        t1.join(timeout=5)
        t2.join(timeout=5)

        assert qa.call_count == 1, "the LLM must be invoked once for one level"
        assert {r[0] for r in results} == {"A generated summary."}
        assert True in {r[1] for r in results}, "one caller should report a cache hit"

    def test_parallel_levels_do_not_clobber_the_cache_file(self, tmp_path, paper):
        service = SummarizerService(
            qa_service=StubQAService(), storage_dir=tmp_path, prefetch_workers=4
        )
        service.prefetch(paper)
        _drain(service, paper)

        # All levels must survive in the single JSON file despite parallel writes.
        assert set(service.get_cached_levels(paper)) == set(LEVELS_BY_ID)


class BlockingQAService:
    """Blocks inside answer() until released, so two threads can be forced to
    contend on the same (paper, level)."""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.call_count = 0
        self._lock = threading.Lock()

    def answer(self, *args, **kwargs):
        with self._lock:
            self.call_count += 1
        self.entered.set()
        self.release.wait(timeout=5)
        return GroundedAnswer(
            answer="A generated summary.", citations=[], approved=True, refused=False, attempts=1
        )
