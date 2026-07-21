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

import socket
import logging
import time
from contextlib import contextmanager
from typing import Iterator, Protocol
from uuid import UUID, uuid4

import arxiv
import httpx

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.search.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

#: python-arxiv builds its own urllib opener with no timeout, so a stalled
#: arXiv connection can hang a search request indefinitely. urllib reads the
#: process-wide default socket timeout at connect time, which is the only
#: lever available here.
_ARXIV_SOCKET_TIMEOUT = 15.0


@contextmanager
def _socket_timeout(seconds: float) -> Iterator[None]:
    """Temporarily set the default socket timeout, restoring it on exit.

    Deliberately scoped rather than set once at import: the default socket
    timeout is process-global, and permanently pinning it to a few seconds
    would also apply to unrelated long-lived connections in the same process —
    notably the multi-minute Hugging Face model downloads the embedding engine
    performs on a cold start.
    """
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(previous)


def _normalize_field_of_study(field: object) -> str | None:
    """Extract a lowercase keyword string from one s2FieldsOfStudy entry.

    Semantic Scholar's real API returns a list of dicts like
    {"category": "Computer Science", "source": "external"}, not plain
    strings. `str(field).lower()` on such a dict produces a junk keyword
    like "{'category': 'computer science', 'source': 'external'}". This
    pulls out just the category, while still accepting a plain string
    (defensive — and matches older API responses/test fixtures).
    """
    if isinstance(field, dict):
        category = field.get("category")
        return str(category).lower() if category else None
    if field:
        return str(field).lower()
    return None


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
        # Configure client to avoid long hangs and fetch only what's needed
        self._client = arxiv.Client(
            page_size=10,       # default is 100, which is too much and can timeout
            delay_seconds=1.0,  # default is 3.0 seconds
            num_retries=0       # default is 3 retries which takes minutes to fail if down
        )
        logger.info("ArxivProvider initialized.")

    def _fetch(self, search_query: "arxiv.Search") -> list:
        """Materialize an arXiv result set under a bounded socket timeout.

        `Client.results()` is a lazy generator that does its network I/O while
        being iterated, so the timeout has to cover consumption, not just the
        call. Both callers bound the result count (`max_results` / `id_list`),
        so materializing here is safe.
        """
        with _socket_timeout(_ARXIV_SOCKET_TIMEOUT):
            return list(self._client.results(search_query))

    def get_paper_by_id(self, arxiv_id: str) -> PaperMetadata | None:
        """Fetch paper metadata from arXiv by arXiv ID."""
        logger.info("Arxiv fetch initiated for ID: '%s'", arxiv_id)
        
        # Strip any version suffix (e.g., "1706.03762v5" -> "1706.03762")
        clean_id = arxiv_id.split("v")[0]
        search_query = arxiv.Search(id_list=[clean_id])
        
        try:
            results = self._fetch(search_query)
            if not results:
                logger.warning("No arXiv paper found for ID: %s", clean_id)
                return None
            res = results[0]
            authors = [a.name for a in res.authors]
            
            return PaperMetadata(
                paper_id=uuid4(),
                title=res.title,
                authors=authors,
                publication_year=res.published.year if res.published else None,
                citation_count=None,
                abstract=res.summary,
                doi=res.doi,
                pdf_url=res.pdf_url,
                source=PaperSource.ARXIV,
                venue="arXiv Preprint",
                keywords=["arxiv", clean_id],
            )
        except Exception as e:
            logger.error("Arxiv fetch failed for ID %s: %s", clean_id, e)
            return None

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
            results = self._fetch(search_query)

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
    PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"

    #: Requested once per call and reused, so both search and metadata lookups
    #: draw from the same quota budget.
    FIELDS = "title,authors,year,citationCount,abstract,externalIds,openAccessPdf,venue,s2FieldsOfStudy"

    def __init__(self, api_key: str = "", requests_per_second: float | None = None) -> None:
        """Initialize the Semantic Scholar provider.

        Args:
            api_key: Optional API key. Grants a per-key quota (commonly 1 rps).
            requests_per_second: Override the configured pacing. Tests pass 0
                to disable sleeping.
        """
        self.api_key = api_key
        self._headers = {}
        if api_key:
            self._headers["x-api-key"] = api_key

        settings = get_settings()
        rps = (
            requests_per_second
            if requests_per_second is not None
            else settings.semantic_scholar_rate_limit_rps
        )
        # One limiter per provider instance, and the provider is an lru_cache'd
        # singleton (app/utils.py::get_search_agent), so every request in the
        # process shares one queue against the single per-key quota.
        self._limiter = RateLimiter(rps)
        self._max_retries = settings.semantic_scholar_max_retries
        logger.info("SemanticScholarProvider initialized (rate limit %.2f rps).", rps)

    def _request(self, url: str, params: dict) -> httpx.Response | None:
        """Perform a paced GET, retrying on 429 with exponential backoff.

        Pacing should make 429s rare, but the quota is per *key*, not per
        process — another process (or a second uvicorn worker) sharing the key
        can still push us over. Retrying keeps a search succeeding through that
        instead of silently returning nothing.

        Returns None when the request ultimately failed; callers decide whether
        that means "no results" or "no metadata".
        """
        for attempt in range(self._max_retries + 1):
            self._limiter.acquire()
            with httpx.Client(headers=self._headers, timeout=15.0) as client:
                response = client.get(url, params=params)

            if response.status_code != 429:
                return response

            if attempt == self._max_retries:
                logger.warning(
                    "Semantic Scholar still rate-limited (429) after %d retries.", self._max_retries
                )
                return response

            # Honour Retry-After when the server sends it; otherwise back off
            # exponentially from one full quota interval.
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else max(self._limiter.min_interval, 1.0) * (2 ** attempt)
            except ValueError:
                delay = max(self._limiter.min_interval, 1.0) * (2 ** attempt)

            logger.warning(
                "Semantic Scholar rate-limited (429); retrying in %.1fs (attempt %d/%d).",
                delay,
                attempt + 1,
                self._max_retries,
            )
            time.sleep(delay)

        return None

    def get_paper_by_doi(self, doi: str) -> PaperMetadata | None:
        """Fetch paper metadata from Semantic Scholar by DOI."""
        return self._get_paper_by_external_id(f"DOI:{doi}")

    def get_paper_by_arxiv(self, arxiv_id: str) -> PaperMetadata | None:
        """Fetch paper metadata from Semantic Scholar by ArXiv ID."""
        # Strip version suffix
        clean_id = arxiv_id.split("v")[0]
        return self._get_paper_by_external_id(f"arXiv:{clean_id}")

    def _get_paper_by_external_id(self, ext_id: str) -> PaperMetadata | None:
        logger.info("Semantic Scholar fetch initiated for external ID: '%s'", ext_id)
        url = f"{self.PAPER_URL}/{ext_id}"
        try:
            response = self._request(url, {"fields": self.FIELDS})
            if response is None:
                return None
            if response.status_code == 404:
                logger.warning("No Semantic Scholar paper found for external ID: %s", ext_id)
                return None
            if response.status_code == 429:
                logger.warning("Semantic Scholar rate limited (429) on external ID fetch.")
                return None
            response.raise_for_status()
            item = response.json()

            authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
            ext_ids = item.get("externalIds", {})
            doi = ext_ids.get("DOI")
            arxiv_id = ext_ids.get("ArXiv")

            pdf_url = None
            oa_pdf = item.get("openAccessPdf")
            if oa_pdf and isinstance(oa_pdf, dict):
                pdf_url = oa_pdf.get("url")

            keywords = ["semanticscholar"]
            if arxiv_id:
                keywords.append(arxiv_id)
            fields_of_study = item.get("s2FieldsOfStudy")
            if fields_of_study:
                keywords.extend(kw for kw in (_normalize_field_of_study(f) for f in fields_of_study) if kw)

            return PaperMetadata(
                paper_id=uuid4(),
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
        except Exception as e:
            logger.error("Semantic Scholar fetch failed for external ID %s: %s", ext_id, e)
            return None

    def search(self, query: str, limit: int = 10) -> list[PaperMetadata]:
        """Query Semantic Scholar and parse results into PaperMetadata.

        Args:
            query: Natural language search topic.
            limit: Maximum candidates to fetch.

        Returns:
            List of parsed PaperMetadata objects.
        """
        logger.info("Semantic Scholar search initiated for query: '%s' (limit=%d)", query, limit)

        params = {
            "query": query,
            "limit": limit,
            "fields": self.FIELDS,
        }

        papers: list[PaperMetadata] = []

        try:
            response = self._request(self.API_URL, params)
            if response is None:
                return []

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
                    keywords.extend(kw for kw in (_normalize_field_of_study(f) for f in fields_of_study) if kw)

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
