# Add an OpenAlex search provider

## Background

`src/paperpilot/search/providers.py` defines `SearchProvider` as a
`typing.Protocol` specifically so new sources can be added without
touching `SearchAgent`: *"If we want to add a new search provider in the
future (e.g. OpenAlex or Crossref), we just implement the SearchProvider
protocol and inject it into the SearchAgent."* ROADMAP.md lists "Additional
search providers — e.g. OpenAlex, Crossref" under planned/future work.
Today only `ArxivProvider` and `SemanticScholarProvider` exist.

## Why it matters

OpenAlex is a free, keyless, high-coverage academic metadata API (a
Semantic Scholar alternative/complement with broader venue coverage) and
is exactly the kind of addition the `SearchProvider` protocol was designed
to make cheap. This is a good showcase issue for the architecture: a
well-scoped feature that should require *zero* changes to `SearchAgent`,
`PaperRanker`, or `WorkspaceManager` — only a new class implementing
`search(query, limit) -> list[PaperMetadata]`, following the exact pattern
`SemanticScholarProvider` already establishes (rate limiting via
`RateLimiter`, retry-on-429, `PaperMetadata` field mapping).

## Proposed solution

Add `OpenAlexProvider` implementing the `SearchProvider` protocol, using
[OpenAlex's REST API](https://docs.openalex.org/) (no key required, though
a polite-pool email param is recommended). Map OpenAlex's `Work` schema
fields to `PaperMetadata` (title, authors, publication year, citation
count, abstract — note OpenAlex returns abstracts as an inverted index,
requiring reconstruction — DOI, open-access PDF URL via
`open_access.oa_url`, venue). Register it alongside the existing providers
in `app/utils.py::get_search_agent`.

## Acceptance criteria

- [ ] `OpenAlexProvider.search(query, limit)` returns `list[PaperMetadata]`
      matching the existing contract (same fields populated as the other
      providers, `None`/empty where OpenAlex doesn't have the data).
- [ ] Handles OpenAlex's inverted-index abstract format correctly.
- [ ] Network failures degrade to an empty list (matching
      `ArxivProvider`/`SemanticScholarProvider`'s existing "one provider
      failing shouldn't crash the whole search" behavior).
- [ ] Registered in `get_search_agent` behind a way to enable/disable it
      (a `Settings` flag, consistent with how other providers are always-on
      today — a maintainer may prefer it on by default given it's keyless).
- [ ] Covered by offline tests mocking the OpenAlex HTTP responses,
      following `tests/test_providers.py`'s existing pattern.

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

None.
