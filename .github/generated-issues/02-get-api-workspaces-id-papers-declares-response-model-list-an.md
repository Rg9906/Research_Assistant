---
title: "`GET /api/workspaces/{id}/papers` declares `response_model=List[Any]`, throwing away its schema"
labels: ['good first issue', 'backend', 'bug']
difficulty: Beginner
estimate: "30 min"
category: "🐛 Bug"
---

# `GET /api/workspaces/{id}/papers` declares `response_model=List[Any]`, throwing away its schema

**Category:** 🐛 Bug

## Background

`list_workspace_papers` in `src/app/api.py` is typed `response_model=List[Any]` and manually calls `p.model_dump()` on each `PaperMetadata`. Every other list endpoint in the file returns a typed Pydantic model. `List[Any]` means FastAPI's generated OpenAPI schema (and the interactive `/docs` page) shows no field information for this endpoint at all, and any typo in a downstream frontend consumer goes undetected.

## Why it matters

Contributors exploring the API via `/docs` (a huge onboarding aid for a new open-source project) hit a dead end on one of the four core endpoints. It also silently defeats the type-safety FastAPI + Pydantic otherwise gives the whole project.

## Proposed solution

Change the route's `response_model` to `List[PaperMetadata]` and return the model instances directly (FastAPI serializes Pydantic models on its own — the manual `model_dump()` becomes unnecessary).

## Acceptance Criteria

- [ ] `response_model=List[PaperMetadata]` replaces `List[Any]`
- [ ] `/docs` shows the full `PaperMetadata` schema for this endpoint
- [ ] Existing `tests/test_api.py` coverage for this endpoint still passes unmodified (response JSON shape is unchanged)

## Suggested files

`src/app/api.py`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, backend, bug

## Dependencies

None
