# Reuse a persistent `httpx.Client` in `SemanticScholarProvider`

## Background

`SemanticScholarProvider._request()` (`src/paperpilot/search/providers.py`)
opens a brand-new `httpx.Client` for every single HTTP call, including
retries:

```python
def _request(self, url: str, params: dict) -> httpx.Response | None:
    for attempt in range(self._max_retries + 1):
        self._limiter.acquire()
        with httpx.Client(headers=self._headers, timeout=15.0) as client:
            response = client.get(url, params=params)
        ...
```

`SemanticScholarProvider` is itself a long-lived singleton (constructed
once via `app/utils.py::get_search_agent`, which is `lru_cache`'d), so
there's no reason each request needs its own client — every call pays a
fresh TCP + TLS handshake instead of reusing a pooled, keep-alive
connection.

## Why it matters

This is a straightforward, safe performance win: connection reuse
noticeably reduces latency per search request (handshake avoidance) and
reduces load on Semantic Scholar's servers, which matters given this
provider is already rate-limited and retried on 429. It's also a good
example of "the provider is already a cached singleton, so its HTTP client
should be too" — the same reasoning the project already applies to
`SearchAgent`/`PaperRanker`/embedding models via `app/utils.py`'s
`lru_cache`s.

## Proposed solution

Create the `httpx.Client` once in `__init__` and reuse it for the
provider's lifetime:

```python
def __init__(self, api_key: str = "", requests_per_second: float | None = None) -> None:
    ...
    self._client = httpx.Client(headers=self._headers, timeout=15.0)

def _request(self, url: str, params: dict) -> httpx.Response | None:
    for attempt in range(self._max_retries + 1):
        self._limiter.acquire()
        response = self._client.get(url, params=params)
        ...
```

Since headers can differ if the API key is set at construction time
(`self._headers` is built once in `__init__` already), passing them to the
client constructor once is equivalent to passing them per-request today.
No behavior change — this is purely a connection-reuse optimization.

## Acceptance criteria

- [ ] `SemanticScholarProvider` constructs one `httpx.Client` and reuses it
      across all requests (search, DOI/arXiv metadata lookups, retries).
- [ ] No behavior change to retry/backoff logic, headers, or timeouts.
- [ ] Existing tests in `tests/test_providers.py` continue to pass (they
      likely mock `httpx.Client` — update the mock target if it's currently
      patching the per-call `with httpx.Client(...)` construction).

## Suggested files

- `src/paperpilot/search/providers.py`
- `tests/test_providers.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

`good first issue`, `performance`, `backend`

## Dependencies

None.
