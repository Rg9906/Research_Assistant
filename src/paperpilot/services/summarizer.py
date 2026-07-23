"""Multi-level paper summarization with persistent caching.

Why a dedicated service (rather than the chat endpoint with a clever prompt):
    The frontend's summary tabs used to fire a normal chat request with a
    hand-written prompt every time a tab was clicked. Three problems with that:
    re-clicking a tab paid for the whole answer again, the summary levels lived
    in the frontend where the backend couldn't reuse them, and summaries shared
    the workspace's *conversation memory* — so a summary generated mid-chat was
    influenced by whatever had been discussed earlier, making it irreproducible.

    Summaries are per-paper, deterministic-by-intent artifacts, so they belong
    in a service that owns the level definitions, generates each one with no
    conversation history, and caches the result on disk next to the paper's
    index. A cache hit costs no LLM call at all.

Why grounded generation:
    Summaries go through the same GroundedQAService as chat, so a summary is
    held to the same standard as an answer: written only from retrieved chunks,
    audited by the critic, and refused when the paper doesn't support it. A
    hallucinated "Limitations" section is exactly the failure mode this project
    exists to avoid.

Cache invalidation:
    The cache is keyed by paper and level and stored in the paper's storage
    directory, which is itself rebuilt whenever the index fingerprint changes
    (different PDF, embed model, or chunk params — see PaperSessionManager).
    Re-indexing a paper therefore drops its stale summaries with it.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata
from paperpilot.services.grounded_qa import GroundedAnswer, GroundedQAService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryLevel:
    """One summary view: what to ask for, and at what explanation level."""

    id: str
    label: str
    prompt: str
    difficulty: str


#: The summary levels from the vision document (ProjectIdea.txt, "Multi-Level
#: Summarization"). Defined here rather than in the frontend so every client —
#: and any future agent — asks for the same thing in the same words.
SUMMARY_LEVELS: tuple[SummaryLevel, ...] = (
    SummaryLevel(
        "quick", "Quick",
        "Summarize this paper in exactly five clear sentences covering the problem, "
        "the proposed approach, and the main result.",
        "undergraduate",
    ),
    SummaryLevel(
        "beginner", "Beginner",
        "Explain this paper as if to an undergraduate student. Avoid heavy jargon, "
        "and define every technical term you use.",
        "beginner",
    ),
    SummaryLevel(
        "technical", "Technical",
        "Give a graduate-researcher-level technical explanation of this paper, "
        "focusing on the methodology and any mathematical or algorithmic detail.",
        "graduate/expert",
    ),
    SummaryLevel(
        "contributions", "Contributions",
        "List this paper's key contributions as concise bullet points.",
        "graduate/expert",
    ),
    SummaryLevel(
        "methodology", "Methodology",
        "Explain the proposed method or algorithm step by step, as described by the paper.",
        "graduate/expert",
    ),
    SummaryLevel(
        "results", "Results",
        "Summarize the experimental setup, datasets, baselines, and reported results, "
        "including specific numbers where the paper states them.",
        "graduate/expert",
    ),
    SummaryLevel(
        "limitations", "Limitations",
        "What limitations, weaknesses, or threats to validity does this paper have? "
        "Include only limitations the paper itself acknowledges or that its stated "
        "results directly demonstrate.",
        "graduate/expert",
    ),
    SummaryLevel(
        "future_work", "Future Work",
        "What future research directions does this paper propose?",
        "graduate/expert",
    ),
    SummaryLevel(
        "prerequisites", "Prerequisites",
        "What concepts should a reader understand before reading this paper? "
        "List them in the order they should be learned.",
        "undergraduate",
    ),
    SummaryLevel(
        "glossary", "Glossary",
        "Define the technical terms and notation this paper uses, as the paper uses them.",
        "undergraduate",
    ),
)

LEVELS_BY_ID: Dict[str, SummaryLevel] = {level.id: level for level in SUMMARY_LEVELS}

#: The order background prefetching generates levels in, most-commonly-viewed
#: first, so the tabs a user is most likely to click next are ready soonest.
#: Any level not listed here (e.g. a newly added one) is still prefetched, just
#: after these — see `_prefetch_order`.
PREFETCH_PRIORITY: Tuple[str, ...] = (
    # Priority 1 — the default landing views
    "quick", "beginner",
    # Priority 2 — the deep-dive views opened next most often
    "technical", "methodology",
    # Priority 3
    "contributions", "results",
    # Priority 4 — the long tail
    "limitations", "future_work", "prerequisites", "glossary",
)


class SummarizerService:
    """Generates and caches the multi-level summaries for a paper."""

    CACHE_FILENAME = "summaries.json"

    def __init__(
        self,
        qa_service: GroundedQAService,
        storage_dir: Optional[Path] = None,
        top_k: Optional[int] = None,
        prefetch_workers: Optional[int] = None,
    ) -> None:
        self.qa_service = qa_service
        # Default to the same per-paper directory the index lives in, so a
        # paper's derived artifacts stay together and are cleaned up together.
        self.storage_dir = storage_dir or qa_service.session_manager.base_dir
        settings = get_settings()
        self.top_k = top_k or settings.rag_summary_top_k

        # --- Concurrency machinery for parallel/background generation ---
        # Prefetch and on-demand clicks can now hit the same (paper, level) at
        # once. A per-key lock guarantees exactly one LLM generation per key: a
        # second caller blocks, then finds the cache populated and returns it,
        # so parallelism never turns into duplicate LLM calls.
        self._key_locks: Dict[Tuple[str, str], threading.Lock] = {}
        self._key_locks_guard = threading.Lock()
        # The on-disk cache is one JSON file per paper. Two levels finishing at
        # once would otherwise read-modify-write it concurrently and clobber
        # each other, so writes for a paper are serialized by a per-paper lock.
        self._file_locks: Dict[str, threading.Lock] = {}
        self._file_locks_guard = threading.Lock()
        # Levels queued or running in the background, for dedup + status.
        self._scheduled: set[Tuple[str, str]] = set()
        self._scheduled_guard = threading.Lock()

        self._prefetch_workers = prefetch_workers or settings.rag_prefetch_workers
        # Lazily created so a process that never prefetches (e.g. the test suite)
        # spawns no threads.
        self._executor: Optional[ThreadPoolExecutor] = None
        self._executor_guard = threading.Lock()

    def _get_key_lock(self, paper_id: UUID, level_id: str) -> threading.Lock:
        key = (str(paper_id), level_id)
        with self._key_locks_guard:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    def _get_file_lock(self, paper_id: UUID) -> threading.Lock:
        key = str(paper_id)
        with self._file_locks_guard:
            lock = self._file_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._file_locks[key] = lock
            return lock

    def _get_executor(self) -> ThreadPoolExecutor:
        with self._executor_guard:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self._prefetch_workers,
                    thread_name_prefix="summary-prefetch",
                )
            return self._executor

    @staticmethod
    def _retrieval_query(paper: PaperMetadata) -> str:
        """Build a content-bearing query representing the paper itself.

        The title alone is short and often stylised; adding the abstract gives
        the embedding enough signal to pull the paper's substantive passages.
        """
        parts = [paper.title]
        if paper.abstract:
            parts.append(paper.abstract)
        return "\n".join(parts)

    def _cache_path(self, paper: PaperMetadata) -> Path:
        return self.storage_dir / f"paper_{paper.paper_id}" / self.CACHE_FILENAME

    def _read_cache(self, paper: PaperMetadata) -> Dict[str, str]:
        path = self._cache_path(paper)
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            # A corrupt cache must never block generation — regenerate instead.
            logger.warning("Ignoring unreadable summary cache %s: %s", path, e)
            return {}

    def _store_summary(self, paper: PaperMetadata, level_id: str, summary: str) -> None:
        """Merge one level into the paper's cache file atomically.

        Re-reads under the per-paper lock before writing so a concurrent write
        of a *different* level (during parallel prefetch) can't clobber this
        one — the previous read-modify-write outside a lock did exactly that.
        """
        with self._get_file_lock(paper.paper_id):
            cache = self._read_cache(paper)
            cache[level_id] = summary
            path = self._cache_path(paper)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, indent=2)
            except OSError as e:
                # Losing the cache costs money and latency, not correctness.
                logger.warning("Could not persist summary cache %s: %s", path, e)

    def get_cached_levels(self, paper: PaperMetadata) -> List[str]:
        """Which levels are already generated (so the UI can show them instantly)."""
        return sorted(self._read_cache(paper).keys())

    def summarize(
        self,
        paper: PaperMetadata,
        level_id: str,
        regenerate: bool = False,
    ) -> tuple[str, bool]:
        """Return `(summary_text, from_cache)` for one level of one paper.

        Args:
            paper: The paper to summarize (must already be indexed).
            level_id: One of `LEVELS_BY_ID`.
            regenerate: Bypass and overwrite the cached value.

        Raises:
            KeyError: if `level_id` is not a known level.
        """
        if level_id not in LEVELS_BY_ID:
            raise KeyError(f"Unknown summary level '{level_id}'. Known: {sorted(LEVELS_BY_ID)}")

        level = LEVELS_BY_ID[level_id]

        # Fast path: serve a cache hit without taking the generation lock, so
        # revisiting an already-generated tab never queues behind an in-flight
        # generation of a different level.
        if not regenerate:
            cache = self._read_cache(paper)
            if level_id in cache:
                logger.info("Summary cache hit for paper %s level '%s'", paper.paper_id, level_id)
                return cache[level_id], True

        # Only one generation per (paper, level) at a time. If a background
        # prefetch is already generating this level, an on-demand click for the
        # same tab blocks here and then returns the freshly cached result below
        # instead of paying for a second identical LLM call.
        with self._get_key_lock(paper.paper_id, level_id):
            if not regenerate:
                cache = self._read_cache(paper)
                if level_id in cache:
                    logger.info(
                        "Summary cache hit (after wait) for paper %s level '%s'",
                        paper.paper_id, level_id,
                    )
                    return cache[level_id], True
            return self._generate_locked(paper, level)

    def _generate_locked(self, paper: PaperMetadata, level: SummaryLevel) -> tuple[str, bool]:
        """Generate one level. Caller must hold that level's key lock."""
        logger.info("Generating '%s' summary for paper '%s'", level.id, paper.title)
        # No chat_history: a summary must not depend on what was discussed
        # before it, or the same tab would render differently per conversation.
        #
        # Retrieval is deliberately *not* driven by the prompt. "Summarize this
        # paper in five sentences" is an instruction, and instructions resemble
        # no passage in the paper — embedding-similarity retrieval scored every
        # chunk below the relevance threshold and the summarizer refused every
        # level. Searching on the paper's own title/abstract returns the
        # passages a summary should actually be built from, and the cutoff is
        # disabled because a summary wants broad coverage, not the few chunks
        # closest to one query.
        result: GroundedAnswer = self.qa_service.answer(
            papers=[paper],
            question=level.prompt,
            chat_history=None,
            difficulty=level.difficulty,
            retrieval_query=self._retrieval_query(paper),
            similarity_top_k=self.top_k,
            apply_similarity_cutoff=False,
        )

        # Refusals aren't cached: they usually mean retrieval missed rather than
        # that the paper genuinely lacks the content, and caching one would make
        # a transient miss permanent.
        if result.refused:
            logger.warning("Summary '%s' refused for paper '%s'", level.id, paper.title)
            return result.answer, False

        self._store_summary(paper, level.id, result.answer)
        return result.answer, False

    # -- Background prefetching -------------------------------------------------

    def _prefetch_order(self, cached: set[str]) -> List[str]:
        """Levels still to generate, in priority order.

        PREFETCH_PRIORITY first, then any other known level (so a newly added
        level is still warmed, just after the prioritized ones).
        """
        ordered = [lid for lid in PREFETCH_PRIORITY if lid in LEVELS_BY_ID]
        ordered += [lid for lid in LEVELS_BY_ID if lid not in PREFETCH_PRIORITY]
        return [lid for lid in ordered if lid not in cached]

    def prefetch(self, paper: PaperMetadata) -> Dict[str, List[str]]:
        """Kick off background generation of every not-yet-cached level.

        Returns immediately with the current status. Work runs on a bounded
        pool (`rag_prefetch_workers`), submitted in priority order so the
        most-viewed tabs are ready first. Idempotent: a level already cached or
        already scheduled is skipped, so repeated calls (React re-mounts, a
        second browser tab) never double-generate.
        """
        cached = set(self.get_cached_levels(paper))
        newly_scheduled: List[str] = []

        for level_id in self._prefetch_order(cached):
            key = (str(paper.paper_id), level_id)
            with self._scheduled_guard:
                if key in self._scheduled:
                    continue
                self._scheduled.add(key)
            newly_scheduled.append(level_id)
            self._get_executor().submit(self._prefetch_one, paper, level_id)

        pending = self.pending_levels(paper)
        logger.info(
            "Prefetch for paper %s: %d cached, %d scheduled now, %d pending total",
            paper.paper_id, len(cached), len(newly_scheduled), len(pending),
        )
        return {"cached": sorted(cached), "pending": pending}

    def _prefetch_one(self, paper: PaperMetadata, level_id: str) -> None:
        key = (str(paper.paper_id), level_id)
        try:
            self.summarize(paper, level_id)
        except Exception:
            # A prefetch failure must never crash the pool or block other
            # levels; the tab will simply generate on demand when clicked.
            logger.exception("Background prefetch failed for paper %s level '%s'",
                             paper.paper_id, level_id)
        finally:
            with self._scheduled_guard:
                self._scheduled.discard(key)

    def pending_levels(self, paper: PaperMetadata) -> List[str]:
        """Levels currently queued or generating in the background."""
        prefix = str(paper.paper_id)
        with self._scheduled_guard:
            return sorted(lid for (pid, lid) in self._scheduled if pid == prefix)

    def status(self, paper: PaperMetadata) -> Dict[str, List[str]]:
        """What's ready vs still being prepared, for the UI to poll."""
        return {
            "cached": self.get_cached_levels(paper),
            "pending": self.pending_levels(paper),
        }
