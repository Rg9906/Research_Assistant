---
title: "Standardize FastAPI endpoint response shapes across `app/api.py`"
labels: ['refactor', 'backend', 'api']
difficulty: Medium
estimate: "1 day"
category: "🏗 Refactor"
---

# Standardize FastAPI endpoint response shapes across `app/api.py`

**Category:** 🏗 Refactor

## Background

Endpoints in `src/app/api.py` return inconsistent shapes: some use a typed `response_model` (`WorkspaceResponse`, `ChatResponse`, `SummaryResponse`), others return a bare dict (`{"results": [...]}` from `/api/search`, `{"workspace_id": ...}` from `/api/papers/process`, `{"levels": [...]}` from `/api/summary-levels`). None of this is wrong per se, but it means a frontend developer (or an external API consumer) can't rely on one consistent envelope shape across the API.

## Why it matters

As this project attracts contributors building against its API (including its own frontend), a consistent response contract measurably reduces the number of "wait, is it `.results` or a bare array?" bugs.

## Proposed solution

Define typed `response_model`s for the remaining ad-hoc dict-returning endpoints (`SearchResponse`, `ProcessPaperResponse`, `SummaryLevelsResponse`) and use them consistently. This is a larger, cross-cutting change — discuss the exact target shape in the tracking issue before opening a PR, per CONTRIBUTING.md's guidance on architecture-adjacent changes.

## Acceptance Criteria

- [ ] Every endpoint in `app/api.py` has an explicit `response_model`
- [ ] The frontend's `src/api/client.ts` is updated to match any shape changes
- [ ] `tests/test_api.py` is updated accordingly and the OpenAPI schema at `/docs` documents every response fully

## Suggested files

`src/app/api.py`, `frontend/src/api/client.ts`, `tests/test_api.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

refactor, backend, api

## Dependencies

None
