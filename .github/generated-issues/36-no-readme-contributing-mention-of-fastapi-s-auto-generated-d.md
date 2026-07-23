---
title: "No README/CONTRIBUTING mention of FastAPI's auto-generated `/docs` and `/redoc`"
labels: ['good first issue', 'documentation']
difficulty: Beginner
estimate: "10 min"
category: "📚 Documentation"
---

# No README/CONTRIBUTING mention of FastAPI's auto-generated `/docs` and `/redoc`

**Category:** 📚 Documentation

## Background

FastAPI automatically serves interactive Swagger UI at `/docs` and ReDoc at `/redoc` for the running backend — a genuinely excellent, zero-effort way for a contributor to explore every endpoint's request/response schema. Neither README.md's Quick Start nor CONTRIBUTING.md's Development Setup mentions this exists.

## Why it matters

This is a free onboarding win: pointing a new contributor at `http://localhost:8000/docs` right after step 5 of the Quick Start ("Run the backend") gives them an interactive map of the entire API surface with zero additional work from the maintainer.

## Proposed solution

Add one or two lines to README.md's Quick Start (after "Run the backend") and CONTRIBUTING.md's Development Setup pointing to `/docs` and `/redoc`.

## Acceptance Criteria

- [ ] README.md and CONTRIBUTING.md both mention `/docs` and `/redoc` in the backend setup steps

## Suggested files

`README.md`, `CONTRIBUTING.md`

## Difficulty

Beginner

## Estimated time

10 min

## Labels

good first issue, documentation

## Dependencies

None
