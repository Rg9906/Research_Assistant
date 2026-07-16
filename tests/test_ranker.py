"""
Unit tests for the multi-factor paper ranker.

These tests mock the EmbeddingEngine to verify the mathematical ranking
logic (log-scaled citations, exponential recency decay, and weighted sums)
remains correct, deterministic, and handles edge cases properly.
"""

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np
import pytest

from paperpilot.core.models import PaperMetadata
from paperpilot.search.ranker import PaperRanker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_paper(title: str, year: int | None, citations: int | None) -> PaperMetadata:
    """Create a minimal PaperMetadata instance for testing."""
    return PaperMetadata(
        title=title,
        publication_year=year,
        citation_count=citations,
        abstract="Test abstract",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPaperRanker:
    """Unit tests for the PaperRanker class."""

    def test_ranking_math_correctness(self):
        """Verify the weighted score calculation matches the formulas."""
        # 1. Setup mock embedding engine
        # We want to mock embeddings so we can control similarity exactly.
        # dot product between query [1.0, 0.0] and paper [0.8, 0.6] is 0.8.
        mock_engine = MagicMock()
        mock_engine.embed_query.return_value = np.array([1.0, 0.0], dtype=np.float32)
        mock_engine.embed_texts.return_value = np.array(
            [[0.8, 0.6], [0.5, 0.866]], dtype=np.float32
        )

        # 2. Instantiate ranker with exact weights
        # w_sim = 0.5, w_cit = 0.3, w_rec = 0.2
        # decay_rate = 0.05
        ranker = PaperRanker(
            engine=mock_engine,
            weight_similarity=0.5,
            weight_citations=0.3,
            weight_recency=0.2,
            decay_rate=0.05,
        )

        current_year = datetime.now().year
        papers = [
            _make_paper("Paper A", year=current_year, citations=100),       # Age 0, Cit 100
            _make_paper("Paper B", year=current_year - 10, citations=1000),  # Age 10, Cit 1000
        ]

        # 3. Compute expected scores manually
        # Max citations is 1000.
        # Paper A:
        #   - Similarity = 0.8
        #   - Citations score = log(1 + 100) / log(1 + 1000) = log(101) / log(1001) = 4.615 / 6.909 = ~0.668
        #   - Recency score = e^(-0.05 * 0) = 1.0
        #   - Expected total = 0.5 * 0.8 + 0.3 * 0.668 + 0.2 * 1.0 = 0.4 + 0.2004 + 0.2 = ~0.8004
        #
        # Paper B:
        #   - Similarity = 0.5
        #   - Citations score = log(1 + 1000) / log(1 + 1000) = 1.0
        #   - Recency score = e^(-0.05 * 10) = e^(-0.5) = ~0.6065
        #   - Expected total = 0.5 * 0.5 + 0.3 * 1.0 + 0.2 * 0.6065 = 0.25 + 0.3 + 0.1213 = ~0.6713

        ranked_results = ranker.rank_papers("transformer", papers)

        assert len(ranked_results) == 2
        
        # Verify ordering: Paper A (0.80) should be ranked above Paper B (0.67)
        assert ranked_results[0][0].title == "Paper A"
        assert ranked_results[1][0].title == "Paper B"

        # Verify exact scores match mathematical expectations
        score_a = ranked_results[0][1]
        score_b = ranked_results[1][1]

        assert pytest.approx(score_a, abs=1e-3) == 0.8004
        assert pytest.approx(score_b, abs=1e-3) == 0.6713

    def test_ranking_weights_normalization(self):
        """If weights do not sum to 1.0, the ranker should normalize them."""
        mock_engine = MagicMock()
        mock_engine.embed_query.return_value = np.array([1.0], dtype=np.float32)
        mock_engine.embed_texts.return_value = np.array([[1.0]], dtype=np.float32)

        # Set weights that sum to 2.0 (should divide each by 2)
        ranker = PaperRanker(
            engine=mock_engine,
            weight_similarity=1.0,
            weight_citations=0.6,
            weight_recency=0.4,
        )

        assert ranker.w_sim == 0.5
        assert ranker.w_cit == 0.3
        assert ranker.w_rec == 0.2

    def test_ranking_missing_metadata(self):
        """Missing publication years or citation counts should fall back gracefully."""
        mock_engine = MagicMock()
        mock_engine.embed_query.return_value = np.array([1.0], dtype=np.float32)
        mock_engine.embed_texts.return_value = np.array([[0.8]], dtype=np.float32)

        ranker = PaperRanker(
            engine=mock_engine,
            weight_similarity=0.5,
            weight_citations=0.3,
            weight_recency=0.2,
        )

        paper = _make_paper("Paper with empty metadata", year=None, citations=None)

        results = ranker.rank_papers("test", [paper])
        
        # Verify no crash
        assert len(results) == 1
        # Citations defaults to 0 score. Recency year=None defaults to 0.5.
        # Score = 0.5 * 0.8 + 0.3 * 0.0 + 0.2 * 0.5 = 0.4 + 0.0 + 0.1 = 0.5
        assert pytest.approx(results[0][1], abs=1e-5) == 0.5

    def test_ranking_empty_candidates(self):
        """Ranking an empty candidate list should return an empty list."""
        mock_engine = MagicMock()
        ranker = PaperRanker(engine=mock_engine)
        assert ranker.rank_papers("test", []) == []
