# Add a Crossref search provider

## Background

Same rationale as #020: `SearchProvider` is a `Protocol` specifically
designed so new sources plug in without touching `SearchAgent`, and
ROADMAP.md names Crossref explicitly alongside OpenAlex as a planned
addition.

## Why it matters

Crossref is the canonical source for DOI metadata and covers a huge swath
of published (non-preprint) literature that arXiv doesn't index and
Semantic Scholar sometimes lacks full metadata for. Adding it strengthens
result coverage for exactly the kind of paper (older, non-CS, published
outside major preprint servers) where the current two providers are
weakest.

## Proposed solution

Add `CrossrefProvider` implementing `SearchProvider`, using the free,
keyless [Crossref REST API](https://api.crossref.org/) (`/works` endpoint).
Map Crossref's response fields to `PaperMetadata` (title, authors,
published date, DOI — Crossref is DOI-native — abstract when present,
venue via `container-title`). Note Crossref generally does *not* provide
direct PDF links (most Crossref-indexed works are paywalled or require
resolving the DOI to a publisher page), so `pdf_url` will often be `None`
for these results — which is fine, since `search/availability.py`'s
ranking already deprioritizes abstract-only results and the "No PDF" badge
already communicates this to the user.

## Acceptance criteria

- [ ] `CrossrefProvider.search(query, limit)` returns `list[PaperMetadata]`
      matching the existing contract.
- [ ] Network failures degrade to an empty list, matching existing
      providers.
- [ ] Registered in `get_search_agent`.
- [ ] Covered by offline tests mocking Crossref HTTP responses.

## Suggested files

- `src/paperpilot/search/providers.py`
- `src/app/utils.py`
- `tests/test_providers.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

`enhancement`, `backend`, `feature`

## Dependencies

None. Can be done independently of, or alongside, #020.
