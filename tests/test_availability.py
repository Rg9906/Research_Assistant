"""Tests for PDF availability grading and arXiv URL recovery.

These cover the judgement the ranker leans on to prefer chattable papers, and
the recovery step that turns a Semantic Scholar record with only a publisher
landing page (but an ArXiv external id) into a downloadable one.
"""

from paperpilot.core.models import PaperMetadata, PaperSource
from paperpilot.search.availability import (
    SCORE_DIRECT,
    SCORE_LANDING,
    SCORE_NONE,
    SCORE_OPEN_REPOSITORY,
    apply_best_pdf_url,
    extract_arxiv_id,
    is_pdf_available,
    pdf_availability_score,
    resolve_pdf_url,
    score_pdf_url,
)


class TestScorePdfUrl:
    def test_none_and_empty(self):
        assert score_pdf_url(None) == SCORE_NONE
        assert score_pdf_url("") == SCORE_NONE
        assert score_pdf_url("   ") == SCORE_NONE

    def test_non_http_scheme_is_unusable(self):
        # PDFDownloader allowlists http/https; file:// is a dead end here.
        assert score_pdf_url("file:///etc/paper.pdf") == SCORE_NONE
        assert score_pdf_url("ftp://host/paper.pdf") == SCORE_NONE

    def test_open_repository_scores_highest(self):
        assert score_pdf_url("https://arxiv.org/pdf/1706.03762.pdf") == SCORE_OPEN_REPOSITORY
        assert score_pdf_url("https://www.biorxiv.org/content/x.full.pdf") == SCORE_OPEN_REPOSITORY
        assert score_pdf_url("https://aclanthology.org/2020.acl-main.1.pdf") == SCORE_OPEN_REPOSITORY

    def test_direct_pdf_on_arbitrary_host(self):
        assert score_pdf_url("https://example.com/papers/foo.pdf") == SCORE_DIRECT

    def test_landing_page(self):
        assert score_pdf_url("https://link.springer.com/article/10.1007/x") == SCORE_LANDING


class TestExtractArxivId:
    def test_from_keyword(self):
        paper = PaperMetadata(title="t", keywords=["semanticscholar", "1706.03762"])
        assert extract_arxiv_id(paper) == "1706.03762"

    def test_legacy_id_from_keyword(self):
        paper = PaperMetadata(title="t", keywords=["arxiv", "physics/0405022"])
        assert extract_arxiv_id(paper) == "physics/0405022"

    def test_from_url(self):
        paper = PaperMetadata(title="t", pdf_url="https://arxiv.org/abs/1810.04805v1")
        assert extract_arxiv_id(paper) == "1810.04805"

    def test_from_arxiv_doi(self):
        paper = PaperMetadata(title="t", doi="10.48550/arXiv.1706.03762")
        assert extract_arxiv_id(paper) == "1706.03762"

    def test_absent(self):
        paper = PaperMetadata(title="t", keywords=["computer science"], doi="10.1000/xyz")
        assert extract_arxiv_id(paper) is None


class TestResolvePdfUrl:
    def test_derives_arxiv_url_over_landing_page(self):
        # The classic Semantic Scholar case: an openAccessPdf landing page plus
        # an ArXiv id in keywords. The arXiv copy is what actually downloads.
        paper = PaperMetadata(
            title="t",
            pdf_url="https://publisher.example.com/article/abc",
            keywords=["semanticscholar", "1706.03762"],
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        assert resolve_pdf_url(paper) == "https://arxiv.org/pdf/1706.03762.pdf"

    def test_keeps_existing_open_repository_url(self):
        paper = PaperMetadata(
            title="t",
            pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
            keywords=["arxiv", "1706.03762"],
        )
        assert resolve_pdf_url(paper) == "https://arxiv.org/pdf/1706.03762.pdf"

    def test_keeps_direct_pdf_when_no_arxiv_id(self):
        paper = PaperMetadata(title="t", pdf_url="https://example.com/foo.pdf")
        assert resolve_pdf_url(paper) == "https://example.com/foo.pdf"

    def test_none_when_nothing_usable(self):
        paper = PaperMetadata(title="t")
        assert resolve_pdf_url(paper) is None


class TestApplyBestPdfUrl:
    def test_rewrites_landing_page_to_arxiv(self):
        paper = PaperMetadata(
            title="t",
            pdf_url="https://publisher.example.com/article/abc",
            keywords=["semanticscholar", "1706.03762"],
        )
        apply_best_pdf_url(paper)
        assert paper.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"

    def test_leaves_unavailable_paper_untouched(self):
        paper = PaperMetadata(title="t")
        apply_best_pdf_url(paper)
        assert paper.pdf_url is None


class TestAvailabilityScoreAndFlag:
    def test_score_and_flag_agree(self):
        openable = PaperMetadata(title="t", pdf_url="https://arxiv.org/pdf/1706.03762.pdf")
        abstract_only = PaperMetadata(title="t")

        assert pdf_availability_score(openable) == SCORE_OPEN_REPOSITORY
        assert is_pdf_available(openable) is True

        assert pdf_availability_score(abstract_only) == SCORE_NONE
        assert is_pdf_available(abstract_only) is False

    def test_recovered_arxiv_paper_is_available(self):
        # No pdf_url, but an ArXiv id -> availability comes from the derived link.
        paper = PaperMetadata(title="t", keywords=["semanticscholar", "1706.03762"])
        assert is_pdf_available(paper) is True
        assert pdf_availability_score(paper) == SCORE_OPEN_REPOSITORY
