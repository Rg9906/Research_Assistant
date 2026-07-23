"""How likely a discovered paper is to be readable — and therefore chattable.

Why this module exists:
    Every feature past discovery (indexing, chat, the ten summary levels) needs
    the PDF. A search result without a downloadable PDF is an abstract and a
    dead end: the user clicks through, waits, and gets "Cannot process paper
    without a PDF URL". Relevance alone is therefore the wrong sort key — a
    marginally-less-relevant paper we can actually open beats a perfect one we
    cannot.

    Not every `pdf_url` is equal either. arXiv links are effectively guaranteed
    to be a real PDF; Semantic Scholar's `openAccessPdf` frequently points at a
    publisher landing page that serves HTML and fails in `PDFDownloader` with
    `PDFUnavailableError`. So this module grades availability on a scale rather
    than as a boolean, and the ranker consumes the grade as a scoring dimension.

    It also *recovers* availability: an S2 record with an ArXiv external id but
    no `openAccessPdf` is fully downloadable via a derived arxiv.org URL. That
    turns a large slice of "no PDF" results into chattable ones.

Kept separate from `ranker.py` because the API layer and the deduplicator need
the same judgement, and CLAUDE.md §6 prefers one shared helper over the same
rule re-derived at three call sites.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from paperpilot.core.models import PaperMetadata

# --- Availability tiers -----------------------------------------------------
#: No usable link at all, or a scheme PDFDownloader refuses (file://, ftp://).
SCORE_NONE = 0.0
#: A link that exists but doesn't look like a file — typically a publisher
#: landing/abstract page. Often HTML, so indexing may still fail.
SCORE_LANDING = 0.45
#: A direct ".pdf" link on an arbitrary host. Usually works; sometimes paywalled.
SCORE_DIRECT = 0.80
#: A known open-access repository. As close to guaranteed as we get.
SCORE_OPEN_REPOSITORY = 1.0

#: Hosts that serve open-access PDFs without paywalls, cookie walls, or
#: JS-rendered interstitials. Matched on suffix so subdomains count
#: ("www.biorxiv.org", "proceedings.neurips.cc").
_OPEN_REPOSITORY_HOSTS = (
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "aclanthology.org",
    "openreview.net",
    "ncbi.nlm.nih.gov",
    "europepmc.org",
    "mlr.press",
    "nips.cc",
    "neurips.cc",
    "thecvf.com",
    "jmlr.org",
)

#: arXiv short-id shapes: modern "1706.03762" and legacy "physics/0405022".
_ARXIV_ID_PATTERN = re.compile(r"^(\d{4}\.\d{4,5}|[a-zA-Z\-]+(?:\.[a-zA-Z\-]+)*/\d{7})$")

#: arXiv id embedded in a URL, with any version suffix.
_ARXIV_URL_PATTERN = re.compile(
    r"arxiv\.org/(?:pdf|abs)/(\d{4}\.\d{4,5}|[a-zA-Z\-]+(?:\.[a-zA-Z\-]+)*/\d{7})",
    re.IGNORECASE,
)


def arxiv_pdf_url(arxiv_id: str) -> str:
    """Build the canonical arXiv PDF URL for a short id."""
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def extract_arxiv_id(paper: PaperMetadata) -> str | None:
    """Recover a paper's arXiv short id from its keywords, URL, or DOI.

    Both providers stash the id in `keywords` (arXiv as ["arxiv", "<id>"],
    Semantic Scholar as ["semanticscholar", "<id>"] when `externalIds.ArXiv` is
    present), so a bare id-shaped keyword is treated as authoritative. The URL
    and DOI checks are fallbacks for records that came from elsewhere.
    """
    for kw in paper.keywords:
        if _ARXIV_ID_PATTERN.match(kw.strip()):
            return kw.strip()

    if paper.pdf_url:
        match = _ARXIV_URL_PATTERN.search(paper.pdf_url)
        if match:
            return match.group(1)

    # arXiv-registered DOIs look like 10.48550/arXiv.1706.03762.
    if paper.doi:
        match = re.search(r"arxiv\.(\d{4}\.\d{4,5})", paper.doi, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def score_pdf_url(url: str | None) -> float:
    """Grade a single URL on how likely it is to yield an indexable PDF."""
    if not url or not url.strip():
        return SCORE_NONE

    parsed = urlparse(url.strip())
    # PDFDownloader allowlists http/https; anything else is unusable here even
    # though the string is non-empty.
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return SCORE_NONE

    host = parsed.netloc.lower().split(":")[0]
    if any(host == h or host.endswith("." + h) for h in _OPEN_REPOSITORY_HOSTS):
        return SCORE_OPEN_REPOSITORY

    if parsed.path.lower().endswith(".pdf") or "pdf" in parsed.path.lower().split("/"):
        return SCORE_DIRECT

    return SCORE_LANDING


def resolve_pdf_url(paper: PaperMetadata) -> str | None:
    """The best PDF URL for this paper, deriving an arXiv link if needed.

    Prefers a stored `pdf_url` only when it grades at least as well as the
    derived arXiv one: Semantic Scholar routinely returns a publisher landing
    page for a paper that is also on arXiv, and the arXiv copy is the one that
    actually downloads.
    """
    stored = paper.pdf_url.strip() if paper.pdf_url else None
    stored_score = score_pdf_url(stored)

    arxiv_id = extract_arxiv_id(paper)
    if arxiv_id and stored_score < SCORE_OPEN_REPOSITORY:
        return arxiv_pdf_url(arxiv_id)

    return stored or None


def pdf_availability_score(paper: PaperMetadata) -> float:
    """Grade a paper's PDF availability in [0, 1]. 0 means "abstract only"."""
    return score_pdf_url(resolve_pdf_url(paper))


def is_pdf_available(paper: PaperMetadata) -> bool:
    """Whether the paper can plausibly be downloaded, indexed, and chatted with."""
    return pdf_availability_score(paper) > SCORE_NONE


def apply_best_pdf_url(paper: PaperMetadata) -> PaperMetadata:
    """Write the resolved PDF URL back onto the paper, in place.

    Called once per candidate after de-duplication so that everything
    downstream — the ranker, the API response, `/api/papers/process` — sees the
    same recovered link rather than each re-deriving it (or, worse, the UI
    showing "chattable" for a URL the process endpoint never receives).
    """
    resolved = resolve_pdf_url(paper)
    if resolved and resolved != paper.pdf_url:
        paper.pdf_url = resolved
    return paper
