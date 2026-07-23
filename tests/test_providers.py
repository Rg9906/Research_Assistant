"""
Unit tests for academic search providers.

These tests use unittest.mock to mock network calls to arXiv and Semantic
Scholar, verifying that results are parsed correctly into PaperMetadata objects
and that rate-limiting and connection failures are handled gracefully.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from paperpilot.core.models import PaperSource
from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider


# ---------------------------------------------------------------------------
# ArxivProvider Tests
# ---------------------------------------------------------------------------

class TestArxivProvider:
    """Tests for the ArxivProvider class."""

    @patch("arxiv.Client")
    def test_search_success(self, mock_client_class):
        """Should parse arXiv results correctly into PaperMetadata objects."""
        # Create a mock result
        mock_result = MagicMock()
        mock_result.title = "Attention Is All You Need"
        mock_author = MagicMock()
        mock_author.name = "Ashish Vaswani"
        mock_result.authors = [mock_author]
        mock_result.published = datetime(2017, 6, 12)
        mock_result.summary = "The dominant sequence transduction models..."
        mock_result.doi = "10.48550/arXiv.1706.03762"
        mock_result.pdf_url = "https://arxiv.org/pdf/1706.03762.pdf"
        mock_result.get_short_id.return_value = "1706.03762v5"

        # Mock the client instance
        mock_client = MagicMock()
        mock_client.results.return_value = [mock_result]
        mock_client_class.return_value = mock_client

        provider = ArxivProvider()
        results = provider.search("attention", limit=1)

        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Attention Is All You Need"
        assert paper.authors == ["Ashish Vaswani"]
        assert paper.publication_year == 2017
        assert paper.citation_count is None
        assert paper.source == PaperSource.ARXIV
        assert "1706.03762" in paper.keywords
        assert paper.doi == "10.48550/arXiv.1706.03762"
        assert paper.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"

    @patch("arxiv.Client")
    def test_search_exception_handling(self, mock_client_class):
        """Should catch exceptions and return an empty list rather than crashing."""
        mock_client = MagicMock()
        mock_client.results.side_effect = Exception("Connection Timeout")
        mock_client_class.return_value = mock_client

        provider = ArxivProvider()
        results = provider.search("attention")

        assert results == []


# ---------------------------------------------------------------------------
# SemanticScholarProvider Tests
# ---------------------------------------------------------------------------

class TestSemanticScholarProvider:
    """Tests for the SemanticScholarProvider class."""

    @patch("httpx.Client")
    def test_search_success(self, mock_httpx_client_class):
        """Should parse Semantic Scholar JSON response into PaperMetadata objects."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "authors": [{"name": "Jacob Devlin"}, {"name": "Ming-Wei Chang"}],
                    "year": 2018,
                    "citationCount": 50000,
                    "abstract": "We introduce a new language representation model...",
                    "externalIds": {
                        "DOI": "10.18653/v1/N19-1423",
                        "ArXiv": "1810.04805"
                    },
                    "openAccessPdf": {
                        "url": "https://arxiv.org/pdf/1810.04805.pdf"
                    },
                    "venue": "NAACL-HLT 2019",
                    "s2FieldsOfStudy": ["Computer Science"]
                }
            ]
        }

        # Mock the context manager httpx.Client()
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_httpx_client_class.return_value.__enter__.return_value = mock_client

        provider = SemanticScholarProvider(api_key="fake-key")
        results = provider.search("bert", limit=1)

        assert len(results) == 1
        paper = results[0]
        assert paper.title == "BERT: Pre-training of Deep Bidirectional Transformers"
        assert paper.authors == ["Jacob Devlin", "Ming-Wei Chang"]
        assert paper.publication_year == 2018
        assert paper.citation_count == 50000
        assert paper.source == PaperSource.SEMANTIC_SCHOLAR
        assert paper.doi == "10.18653/v1/N19-1423"
        assert paper.pdf_url == "https://arxiv.org/pdf/1810.04805.pdf"
        assert paper.venue == "NAACL-HLT 2019"
        assert "1810.04805" in paper.keywords
        assert "computer science" in paper.keywords

    @patch("httpx.Client")
    def test_search_extracts_category_from_dict_shaped_fields_of_study(self, mock_httpx_client_class):
        """Real Semantic Scholar responses shape s2FieldsOfStudy as dicts, not strings.

        Regression test: naively stringifying the dict (`str(f).lower()`)
        used to pollute keywords with junk like
        "{'category': 'computer science', 'source': 'external'}".
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "BERT",
                    "authors": [],
                    "year": 2018,
                    "citationCount": 1,
                    "abstract": "",
                    "externalIds": {},
                    "openAccessPdf": None,
                    "venue": "",
                    "s2FieldsOfStudy": [
                        {"category": "Computer Science", "source": "external"},
                        {"category": "Linguistics", "source": "s2-fos-model"},
                    ],
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_httpx_client_class.return_value.__enter__.return_value = mock_client

        provider = SemanticScholarProvider()
        results = provider.search("bert")

        assert len(results) == 1
        keywords = results[0].keywords
        assert "computer science" in keywords
        assert "linguistics" in keywords
        assert not any("{" in kw for kw in keywords)

    @patch("httpx.Client")
    def test_search_rate_limited(self, mock_httpx_client_class):
        """Should handle 429 rate limit codes and return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_httpx_client_class.return_value.__enter__.return_value = mock_client

        provider = SemanticScholarProvider()
        results = provider.search("bert")

        assert results == []

    @patch("httpx.Client")
    def test_search_exception_handling(self, mock_httpx_client_class):
        """Should handle connection errors and return empty list."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("API Server down")
        mock_httpx_client_class.return_value.__enter__.return_value = mock_client

        provider = SemanticScholarProvider()
        results = provider.search("bert")

        assert results == []
