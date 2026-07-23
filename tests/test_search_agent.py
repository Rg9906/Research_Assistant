"""
Unit tests for the Search Agent.

Verifies querying, de-duplication (matching DOIs, matching arXiv IDs, and
title similarity), metadata merging (merging duplicate properties, keeping the
richest fields), and ranking orchestration.
"""

from unittest.mock import MagicMock


from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.search.agent import SearchAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_paper(
    title: str,
    doi: str | None = None,
    keywords: list[str] | None = None,
    authors: list[str] | None = None,
    citations: int | None = None,
    abstract: str | None = None,
    pdf_url: str | None = None,
    source: PaperSource = PaperSource.MANUAL,
) -> PaperMetadata:
    """Helper to generate mock papers for deduplication tests."""
    return PaperMetadata(
        title=title,
        doi=doi,
        keywords=keywords or [],
        authors=authors or [],
        citation_count=citations,
        abstract=abstract,
        pdf_url=pdf_url,
        source=source,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchAgent:
    """Unit tests for the SearchAgent class."""

    def test_deduplicate_by_doi(self):
        """Papers with identical DOIs should be identified as duplicates and merged."""
        paper_a = _make_search_paper(
            title="Attention Is All You Need",
            doi="10.48550/arXiv.1706.03762",
            authors=["Vaswani"],
            abstract="Short abstract",
            source=PaperSource.ARXIV,
        )
        paper_b = _make_search_paper(
            title="Attention Is All You Need (Published)",
            doi="10.48550/arXiv.1706.03762",  # Matching DOI
            authors=["Ashish Vaswani", "Noam Shazeer"],
            citations=100000,
            abstract="Longer abstract with more details...",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )

        mock_provider1 = MagicMock()
        mock_provider1.search.return_value = [paper_a]
        mock_provider2 = MagicMock()
        mock_provider2.search.return_value = [paper_b]
        
        mock_ranker = MagicMock()
        # Mock ranker to return candidates as-is with arbitrary score
        mock_ranker.rank_papers.side_effect = lambda q, papers: [(p, 1.0) for p in papers]

        agent = SearchAgent(
            providers=[mock_provider1, mock_provider2],
            ranker=mock_ranker,
        )

        results = agent.discover_papers("attention", limit_per_provider=5, top_n=5)

        # Verification
        assert len(results) == 1  # Should have merged into 1 paper
        merged_paper = results[0][0]

        # Verify merged properties
        assert merged_paper.doi == "10.48550/arXiv.1706.03762"
        # Keep longer title
        assert merged_paper.title == "Attention Is All You Need (Published)"
        # Combined authors
        assert "Ashish Vaswani" in merged_paper.authors
        assert "Vaswani" in merged_paper.authors
        # Citations merged
        assert merged_paper.citation_count == 100000
        # Keep longer abstract
        assert merged_paper.abstract == "Longer abstract with more details..."

    def test_deduplicate_by_arxiv_id(self):
        """Papers with identical arXiv IDs in their keywords should be merged."""
        paper_a = _make_search_paper(
            title="Transformers",
            keywords=["arxiv", "1706.03762"],
            authors=["Vaswani"],
        )
        paper_b = _make_search_paper(
            title="Transformers",
            keywords=["semanticscholar", "1706.03762"],  # Matching arXiv ID
            authors=["Vaswani"],
        )

        mock_provider = MagicMock()
        mock_provider.search.return_value = [paper_a, paper_b]
        mock_ranker = MagicMock()
        mock_ranker.rank_papers.side_effect = lambda q, papers: [(p, 1.0) for p in papers]

        agent = SearchAgent(providers=[mock_provider], ranker=mock_ranker)
        results = agent.discover_papers("transformers", top_n=5)

        assert len(results) == 1

    def test_deduplicate_by_title_similarity(self):
        """Papers with highly similar titles (Jaccard >= 0.85) should be merged."""
        # Swapped words and minor punctuation differences
        paper_a = _make_search_paper(title="Transformers: Attention Is All You Need")
        paper_b = _make_search_paper(title="Attention Is All You Need: Transformers!")

        mock_provider = MagicMock()
        mock_provider.search.return_value = [paper_a, paper_b]
        mock_ranker = MagicMock()
        mock_ranker.rank_papers.side_effect = lambda q, papers: [(p, 1.0) for p in papers]

        agent = SearchAgent(providers=[mock_provider], ranker=mock_ranker)
        results = agent.discover_papers("transformers", top_n=5)

        assert len(results) == 1

    def test_unique_papers_are_not_merged(self):
        """Distinct papers should not be merged."""
        paper_a = _make_search_paper(title="Attention Is All You Need", doi="10.123/a")
        paper_b = _make_search_paper(title="Pre-training of Deep Bidirectional Transformers", doi="10.123/b")

        mock_provider = MagicMock()
        mock_provider.search.return_value = [paper_a, paper_b]
        mock_ranker = MagicMock()
        mock_ranker.rank_papers.side_effect = lambda q, papers: [(p, 1.0) for p in papers]

        agent = SearchAgent(providers=[mock_provider], ranker=mock_ranker)
        results = agent.discover_papers("ml", top_n=5)

        assert len(results) == 2

    def test_agent_respects_top_n_limit(self):
        """The agent should clamp final results to top_n."""
        papers = [_make_search_paper(title=f"Paper {i}") for i in range(10)]

        mock_provider = MagicMock()
        mock_provider.search.return_value = papers
        mock_ranker = MagicMock()
        mock_ranker.rank_papers.side_effect = lambda q, papers: [(p, 1.0) for p in papers]

        agent = SearchAgent(providers=[mock_provider], ranker=mock_ranker)
        results = agent.discover_papers("test", top_n=3)

        assert len(results) == 3
