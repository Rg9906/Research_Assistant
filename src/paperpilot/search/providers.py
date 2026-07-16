"""
Academic search providers for PaperPilot AI.

This module defines the search provider protocol and concrete client implementations
for querying arXiv and Semantic Scholar.

Why use protocols (interfaces)?
    Using a Protocol (Python's structural typing mechanism, equivalent to interfaces in Java/TS)
    ensures that our SearchAgent remains decoupled from the specific APIs we use.
    If we want to add a new search provider in the future (e.g. OpenAlex or Crossref), we just
    implement the SearchProvider protocol and inject it into the SearchAgent. The agent code
    remains completely unchanged. This satisfies the Open/Closed Principle (SOLID).
"""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID, uuid4

import arxiv
import httpx

from paperpilot.core.models import PaperMetadata, PaperSource

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    """Protocol defining the interface for all academic search providers.

    Any class that implements a search method with this signature is considered
    a SearchProvider and can be used by the SearchAgent.
    """

    def search(self, query: str, limit: int = 10) -> list[PaperMetadata]:
        """Search the academic database for papers matching the query.

        Args:
            query: Natural language query string.
            limit: Maximum number of papers to return.

        Returns:
            A list of PaperMetadata objects matching the search results.
        """
        ...


class ArxivProvider:
    """Search provider querying the arXiv preprint database.

    Uses the official python-arxiv client wrapper to execute queries.
    arXiv is free, requires no API key, and provides open-access PDF links.
    """

    def __init__(self) -> None:
        # Client handles socket timeouts and connection pooling internally
        self._client = arxiv.Client()
        logger.info("ArxivProvider initialized.")

    def search(self, query: str, limit: int = 10) -> list[PaperMetadata]:
        """Query arXiv and parse results into PaperMetadata.

        Args:
            query: Natural language search topic.
            limit: Maximum number of candidates to fetch.

        Returns:
            List of parsed PaperMetadata objects.
        """
        logger.info("Arxiv search initiated for query: '%s' (limit=%d)", query, limit)
        
        # Formulate a general search. arXiv's default SortCriterion is Relevance.
        search_query = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        papers: list[PaperMetadata] = []
        
        try:
            results = self._client.results(search_query)
            
            for res in results:
                # Parse authors: res.authors is a list of arxiv.Result.Author objects
                authors = [a.name for a in res.authors]
                
                # Extract arXiv ID from short_id (e.g. "1706.03762v5" -> "1706.03762")
                arxiv_id = res.get_short_id()
                # strip version suffix if present
                if "v" in arxiv_id:
                    arxiv_id = arxiv_id.split("v")[0]
                
                # Create PaperMetadata
                paper = PaperMetadata(
                    title=res.title,
                    authors=authors,
                    publication_year=res.published.year if res.published else None,
                    citation_count=None,  # arXiv doesn't track citation statistics
                    abstract=res.summary,
                    doi=res.doi,
                    pdf_url=res.pdf_url,
                    source=PaperSource.ARXIV,
                    venue="arXiv Preprint",
                    # Attach arXiv ID in keywords or use it in the deduplication step
                    keywords=["arxiv", arxiv_id],
                )
                papers.append(paper)
                
            logger.info("Arxiv query returned %d matches", len(papers))
            return papers

        except Exception as e:
            logger.error("Arxiv query failed: %s", e)
            # Fail silently by returning an empty list. This ensures one failing provider
            # doesn't crash the entire search step if other providers succeed.
            return []


class SemanticScholarProvider:
    """Search provider querying the Semantic Scholar JSON API.

    Provides rich paper metadata, including citation counts, digital object
    identifiers (DOIs), and peer-reviewed venues.
    """

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: str = "") -> None:
        """Initialize the Semantic Scholar provider.

        Args:
            api_key: Optional API key to bypass default public rate limits.
        """
        self.api_key = api_key
        # We reuse an httpx client for connection pooling
        self._headers = {}
        if api_key:
            self._headers["x-api-key"] = api_key
        logger.info("SemanticScholarProvider initialized.")

    def search(self, query: str, limit: int = 10) -> list[PaperMetadata]:
        """Query Semantic Scholar and parse results into PaperMetadata.

        Args:
            query: Natural language search topic.
            limit: Maximum candidates to fetch.

        Returns:
            List of parsed PaperMetadata objects.
        """
        logger.info("Semantic Scholar search initiated for query: '%s' (limit=%d)", query, limit)

        # Fields to fetch from Semantic Scholar Graph API
        fields = "title,authors,year,citationCount,abstract,externalIds,openAccessPdf,venue,s2FieldsOfStudy"
        params = {
            "query": query,
            "limit": limit,
            "fields": fields,
        }

        papers: list[PaperMetadata] = []

        try:
            with httpx.Client(headers=self._headers, timeout=15.0) as client:
                response = client.get(self.API_URL, params=params)
                
                if response.status_code == 429:
                    logger.warning("Semantic Scholar API rate-limited (429). Returning empty results.")
                    return []
                
                response.raise_for_status()
                data = response.json()

            results = data.get("data", [])
            for item in results:
                # Extract authors
                authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
                
                # Extract IDs
                ext_ids = item.get("externalIds", {})
                doi = ext_ids.get("DOI")
                arxiv_id = ext_ids.get("ArXiv")

                # Extract PDF url
                pdf_url = None
                oa_pdf = item.get("openAccessPdf")
                if oa_pdf and isinstance(oa_pdf, dict):
                    pdf_url = oa_pdf.get("url")

                # Keywords mapping
                keywords = ["semanticscholar"]
                if arxiv_id:
                    keywords.append(arxiv_id)
                fields_of_study = item.get("s2FieldsOfStudy")
                if fields_of_study:
                    keywords.extend([str(f).lower() for f in fields_of_study])

                paper = PaperMetadata(
                    title=item.get("title", ""),
                    authors=authors,
                    publication_year=item.get("year"),
                    citation_count=item.get("citationCount"),
                    abstract=item.get("abstract"),
                    doi=doi,
                    pdf_url=pdf_url,
                    source=PaperSource.SEMANTIC_SCHOLAR,
                    venue=item.get("venue"),
                    keywords=keywords,
                )
                papers.append(paper)

            logger.info("Semantic Scholar query returned %d matches", len(papers))
            return papers

        except Exception as e:
            logger.error("Semantic Scholar query failed: %s", e)
            return []
