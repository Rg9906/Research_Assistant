"""
Search Agent for discovering and ranking research papers.

This module implements the SearchAgent, which queries multiple search providers
(arXiv, Semantic Scholar), merges duplicate results, and ranks them.
"""

from __future__ import annotations

import logging
import re

from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.search.availability import apply_best_pdf_url
from paperpilot.search.providers import SearchProvider
from paperpilot.search.ranker import PaperRanker

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent responsible for paper discovery, de-duplication, and ranking.

    Orchestrates the entire Phase 1 search flow:
    User Query → Fetch from Providers → Deduplicate → Rank → Ranked Results
    """

    def __init__(
        self,
        providers: list[SearchProvider],
        ranker: PaperRanker,
    ) -> None:
        """Initialize the Search Agent.

        Args:
            providers: List of search providers to query (e.g. ArxivProvider, SemanticScholarProvider).
            ranker: PaperRanker instance to score and sort merged results.
        """
        self.providers = providers
        self.ranker = ranker
        logger.info("SearchAgent initialized with %d providers.", len(providers))

    def discover_papers(
        self,
        query: str,
        limit_per_provider: int = 15,
        top_n: int = 10,
    ) -> list[tuple[PaperMetadata, float]]:
        """Query providers, merge duplicates, rank results, and return top_n.

        Args:
            query: Natural language search query.
            limit_per_provider: Maximum number of papers to fetch from each provider.
            top_n: Number of final ranked papers to return.

        Returns:
            A list of (PaperMetadata, total_score) tuples, sorted descending.
        """
        logger.info(
            "Starting paper discovery for query: '%s' (limit_per_provider=%d, top_n=%d)",
            query,
            limit_per_provider,
            top_n,
        )

        # 1. Fetch from all providers
        raw_candidates: list[PaperMetadata] = []
        for provider in self.providers:
            provider_results = provider.search(query, limit=limit_per_provider)
            raw_candidates.extend(provider_results)

        logger.info("Fetched %d raw candidate papers from all providers.", len(raw_candidates))

        # 2. Merge duplicates
        merged_candidates = self._deduplicate_and_merge(raw_candidates)
        logger.info("De-duplication complete: reduced %d raw papers to %d unique papers.", len(raw_candidates), len(merged_candidates))

        # 2b. Recover the best downloadable PDF URL for each paper (e.g. derive
        # an arxiv.org link for a Semantic Scholar record that only had a
        # publisher landing page). Done once here so the ranker, the API
        # response, and /api/papers/process all see the same resolved link —
        # otherwise the UI would flag a paper "chattable" via a URL the process
        # endpoint never receives. Mutates in place after the merge is settled.
        for candidate in merged_candidates:
            apply_best_pdf_url(candidate)

        # 3. Rank merged papers (availability is now one of the scoring factors)
        ranked_results = self.ranker.rank_papers(query, merged_candidates)

        # 4. Limit to top_n
        final_results = ranked_results[:top_n]
        logger.info("Search agent complete. Returning top %d ranked results.", len(final_results))
        return final_results

    def _deduplicate_and_merge(self, candidates: list[PaperMetadata]) -> list[PaperMetadata]:
        """Merge duplicate papers based on DOI, arXiv ID, or title similarity.

        Iteratively parses candidates. If a candidate matches a paper already
        added to the unique pool, we merge their metadata. Otherwise, we add it.
        """
        unique_papers: list[PaperMetadata] = []

        for candidate in candidates:
            matched_index = -1
            
            # Compare candidate against all unique papers found so far
            for idx, unique in enumerate(unique_papers):
                if self._are_duplicates(candidate, unique):
                    matched_index = idx
                    break

            if matched_index >= 0:
                # Merge duplicate metadata into the existing record
                merged = self._merge_metadata(unique_papers[matched_index], candidate)
                unique_papers[matched_index] = merged
                logger.debug("Merged duplicate paper: '%s'", merged.title[:40])
            else:
                unique_papers.append(candidate)

        return unique_papers

    def _are_duplicates(self, a: PaperMetadata, b: PaperMetadata) -> bool:
        """Check if two papers are duplicates of the same publication."""
        # Check 1: Digital Object Identifier (DOI)
        # Most reliable check for published papers
        if a.doi and b.doi:
            if a.doi.strip().lower() == b.doi.strip().lower():
                return True

        # Check 2: arXiv ID
        # Extract arXiv ID if available in keywords
        arxiv_a = self._extract_arxiv_id(a)
        arxiv_b = self._extract_arxiv_id(b)
        if arxiv_a and arxiv_b:
            if arxiv_a == arxiv_b:
                return True

        # Check 3: Semantic Title Similarity (Jaccard Word Similarity)
        # Fallback if both DOIs or arXiv IDs are not present/matched.
        # Catches cases where one provider missing DOI/arXiv ID.
        jaccard_score = self._calculate_title_similarity(a.title, b.title)
        if jaccard_score >= 0.85:
            return True

        return False

    def _extract_arxiv_id(self, paper: PaperMetadata) -> str | None:
        """Helper to extract arXiv short ID from paper keywords.

        arXiv keywords are set in providers as ["arxiv", "1706.03762"]
        """
        if not paper.keywords:
            return None
        
        # Check if the paper keywords contain 'arxiv'
        has_arxiv = False
        arxiv_id = None
        
        # arXiv short IDs follow patterns like 1706.03762 or physics/0405022
        id_pattern = re.compile(r"^(\d{4}\.\d{4,5}|[a-zA-Z\-]+(?:\.[a-zA-Z\-]+)*/\d{7})$")

        for kw in paper.keywords:
            if kw.lower() in ("arxiv", "arxiv preprint"):
                has_arxiv = True
            elif id_pattern.match(kw):
                arxiv_id = kw

        if has_arxiv and arxiv_id:
            return arxiv_id
        
        # Fallback: search abstract or pdf_url for arxiv string
        if paper.pdf_url and "arxiv.org/pdf/" in paper.pdf_url:
            match = re.search(r"/pdf/(\d{4}\.\d{4,5})", paper.pdf_url)
            if match:
                return match.group(1)

        return None

    def _calculate_title_similarity(self, title_a: str, title_b: str) -> float:
        """Calculate word-level Jaccard similarity between two titles.

        Cleans the titles (lowercases, removes punctuation, collapses whitespace)
        and computes overlap. Resilient to punctuation differences and word swaps
        (e.g. "Transformers: Attention is all you need" vs "Attention is all you need: Transformers").
        """
        def clean_to_words(title: str) -> set[str]:
            # Lowercase and replace punctuation with spaces
            cleaned = re.sub(r"[^\w\s]", " ", title.lower())
            # Split into individual words, ignoring empty tokens
            words = set(w for w in cleaned.split() if w.strip())
            return words

        words_a = clean_to_words(title_a)
        words_b = clean_to_words(title_b)

        if not words_a or not words_b:
            return 0.0

        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)

        return len(intersection) / len(union)

    def _merge_metadata(self, primary: PaperMetadata, secondary: PaperMetadata) -> PaperMetadata:
        """Merge duplicate papers, prioritizing richer data.

        Returns a new PaperMetadata object containing the merged values.
        """
        # Title: Prefer the longer, more complete title
        title = primary.title if len(primary.title) >= len(secondary.title) else secondary.title

        # Authors: Union of both author lists (preserving case-insensitive uniqueness)
        author_set = set(primary.authors)
        for auth in secondary.authors:
            if not any(auth.lower() == existing.lower() for existing in author_set):
                author_set.add(auth)
        authors = sorted(list(author_set))

        # Year: Prefer primary, fallback to secondary
        year = primary.publication_year or secondary.publication_year

        # Citation Count: Take the maximum citation count (avoiding None)
        cit_primary = primary.citation_count or 0
        cit_secondary = secondary.citation_count or 0
        citation_count = max(cit_primary, cit_secondary)
        if citation_count == 0 and primary.citation_count is None and secondary.citation_count is None:
            citation_count = None

        # Abstract: Prefer the longer abstract (detailed content)
        abs_p = primary.abstract or ""
        abs_s = secondary.abstract or ""
        abstract = primary.abstract if len(abs_p) >= len(abs_s) else secondary.abstract

        # DOI
        doi = primary.doi or secondary.doi

        # PDF Url
        pdf_url = primary.pdf_url or secondary.pdf_url

        # Venue: Prefer peer-reviewed venues over preprints
        venue = primary.venue
        if not venue or venue == "arXiv Preprint":
            venue = secondary.venue or venue

        # Keywords: Union
        keywords = list(set(primary.keywords + secondary.keywords))

        # Discovered At: Keep earliest timestamp
        discovered_at = min(primary.discovered_at, secondary.discovered_at)

        # Source: Keep primary's source, but if primary is arXiv and secondary is Semantic Scholar,
        # Semantic Scholar might represent richer data. We keep the primary source but log the merge.
        source = primary.source
        if source == PaperSource.MANUAL:
            source = secondary.source

        return PaperMetadata(
            paper_id=primary.paper_id,  # Preserve the original paper ID
            title=title,
            authors=authors,
            publication_year=year,
            citation_count=citation_count,
            abstract=abstract,
            doi=doi,
            pdf_url=pdf_url,
            source=source,
            venue=venue,
            keywords=keywords,
            discovered_at=discovered_at,
        )
