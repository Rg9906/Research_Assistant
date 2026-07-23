---
title: "`/api/search` accepts an unbounded `limit`, letting one request force a huge ranking pass"
labels: ['good first issue', 'backend', 'bug']
difficulty: Beginner
estimate: "30 min"
category: "🐛 Bug"
---

# `/api/search` accepts an unbounded `limit`, letting one request force a huge ranking pass

**Category:** 🐛 Bug

## Background

`SearchQuery.limit` (`src/app/api.py`) is a plain `int` with no upper bound and no lower bound. `SearchAgent.discover_papers(query.query, top_n=query.limit)` forwards it straight into the ranker, which embeds the title+abstract of every candidate paper with `EmbeddingEngine` on every request (`search/ranker.py::rank_papers`). A request with `"limit": 100000` (or a negative number) is accepted as-is and only fails, slowly, deep inside the ranking/embedding step.

## Why it matters

A single client (malicious or just a buggy frontend build) can turn one HTTP request into an expensive, slow embedding job, and there's no clear error message — it just hangs or eventually 500s.

## Proposed solution

Add `Field(gt=0, le=50)` (or whatever ceiling makes sense for the UI) to `SearchQuery.limit`, so FastAPI returns a clean 422 for out-of-range values instead of accepting them.

## Acceptance Criteria

- [ ] `SearchQuery.limit` is constrained with `Field(gt=0, le=<N>)`
- [ ] A request with `limit=0`, a negative limit, or a limit above the ceiling returns HTTP 422 with a clear message
- [ ] A test in `tests/test_api.py` covers the boundary (accepted at the ceiling, rejected just above it)

## Suggested files

`src/app/api.py` (`SearchQuery`), `tests/test_api.py`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, backend, bug

## Dependencies

None
