# Add endpoint tests for `/api/search`

## Background

`POST /api/search` (`src/app/api.py:209-214`, `search_papers`) is the entry
point of the entire product — it's what `DiscoveryFeed.tsx` calls on every
search. It has no endpoint-level test anywhere in `tests/test_api.py`. Only
the underlying `SearchAgent.discover_papers` is unit tested
(`test_search_agent.py`), which never exercises the FastAPI request/response
boundary: the `SearchQuery` request model, the `top_n=query.limit` wiring,
or the `{"results": [...]}` response envelope shape.

## Why it matters

This is the highest-traffic endpoint in the app and the one a new user hits
first. A change to the request/response contract here (accidental or
otherwise) would break the entire discovery flow with no test to catch it.

## Proposed solution

Add a `TestSearchEndpoint` class using `dependency_overrides` to inject a
stub `SearchAgent` (similar to the stub patterns already used for chat).
Cover: a normal query returns the expected envelope shape, `query.limit` is
forwarded correctly as `top_n`, and — once issue #006 (limit validation)
lands — that an out-of-bounds `limit` is rejected with 422 rather than
silently accepted.

## Acceptance criteria

- [ ] A basic search request returns `{"results": [...]}` with expected fields
- [ ] `limit` is verified to be forwarded to `discover_papers(top_n=...)`
- [ ] Test does not hit real arXiv/Semantic Scholar APIs

## Suggested files

- `tests/test_api.py`
- `src/app/api.py:209-214`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, tests, backend

## Dependencies

Pairs with #006 (limit validation) and #029 (its regression test).
