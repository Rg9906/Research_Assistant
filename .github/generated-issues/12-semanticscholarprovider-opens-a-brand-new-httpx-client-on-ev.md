---
title: "`SemanticScholarProvider` opens a brand-new `httpx.Client` on every request attempt"
labels: ['good first issue', 'backend', 'performance']
difficulty: Easy
estimate: "1 hour"
category: "⚡ Performance"
---

# `SemanticScholarProvider` opens a brand-new `httpx.Client` on every request attempt

**Category:** ⚡ Performance

## Background

`SemanticScholarProvider._request` (`src/paperpilot/search/providers.py`) does `with httpx.Client(headers=self._headers, timeout=15.0) as client: client.get(...)` inside the retry loop, so every single HTTP call — including every retry of the same logical request — opens and tears down a new TCP/TLS connection instead of reusing a pooled, keep-alive client.

## Why it matters

Semantic Scholar's free tier is already rate-limited to ~1 rps (see `rate_limit.py`); paying a full TLS handshake on every call adds latency that's pure overhead against an already-scarce quota, and it's an easy fix.

## Proposed solution

Build one `httpx.Client` per `SemanticScholarProvider` instance (it's already an `lru_cache`'d singleton via `app/utils.py::get_search_agent`) and reuse it across calls instead of constructing one per request.

## Acceptance Criteria

- [ ] `SemanticScholarProvider` holds a single reusable `httpx.Client` for its lifetime instead of one per request
- [ ] Existing `tests/test_providers.py` coverage still passes
- [ ] No behavior change to retry/backoff semantics

## Suggested files

`src/paperpilot/search/providers.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, backend, performance

## Dependencies

None
