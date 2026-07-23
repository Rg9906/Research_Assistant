---
title: "No HTTP caching headers on the static `/api/summary-levels` catalogue"
labels: ['good first issue', 'backend', 'performance']
difficulty: Beginner
estimate: "30 min"
category: "⚡ Performance"
---

# No HTTP caching headers on the static `/api/summary-levels` catalogue

**Category:** ⚡ Performance

## Background

`GET /api/summary-levels` (`src/app/api.py`) returns the same, server-defined, hardcoded list of ten `SUMMARY_LEVELS` on every single call — it changes only when the backend is redeployed with a code change. It has no `Cache-Control`/`ETag` response headers, so the frontend refetches it on every relevant page load.

## Why it matters

This is a very small, very safe optimization — a static, rarely-changing payload is a textbook candidate for HTTP caching, and it's requested by both `PaperSummary.tsx` and `WorkspaceDetail.tsx` per CLAUDE.md's request-flow description.

## Proposed solution

Add a long-lived `Cache-Control` header (e.g. `public, max-age=3600`) to the response, or wrap the response in FastAPI's `Response` object with explicit caching headers.

## Acceptance Criteria

- [ ] `GET /api/summary-levels` responses include a `Cache-Control` header
- [ ] A test asserts the header is present with a sensible value

## Suggested files

`src/app/api.py`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, backend, performance

## Dependencies

None
