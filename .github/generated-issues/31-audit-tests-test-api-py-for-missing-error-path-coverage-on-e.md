---
title: "Audit `tests/test_api.py` for missing error-path coverage on every endpoint"
labels: ['tests', 'backend']
difficulty: Medium
estimate: "half day"
category: "🧪 Testing"
---

# Audit `tests/test_api.py` for missing error-path coverage on every endpoint

**Category:** 🧪 Testing

## Background

`tests/test_api.py` has 12 test functions covering an API surface of ~9 endpoints. It's not obvious from a quick read whether every endpoint has both a happy-path *and* an error-path test — for example, does `POST /api/papers/{paper_id}/summary/{level_id}` have a test for the paper-not-found 404 *and* the unknown-level-id 400 *and* the successful-generation *and* the cache-hit paths? Each endpoint should.

## Why it matters

A systematic audit (rather than more ad-hoc tests) is the right first step here — it will likely surface several concrete, easy-to-fix gaps rather than requiring guesswork about what's missing.

## Proposed solution

Go through every route in `app/api.py` and check off, for each: happy path tested, every documented `HTTPException` status code tested, and any FastAPI-level validation error (422) tested. File follow-up issues for any endpoint missing more than one of these.

## Acceptance Criteria

- [ ] A checklist (in the PR description or a short doc) enumerates every endpoint and its current test coverage
- [ ] At least the highest-value gaps found are fixed in the same PR
- [ ] Any remaining gaps are filed as new, specific follow-up issues rather than left implicit

## Suggested files

`tests/test_api.py`

## Difficulty

Medium

## Estimated time

half day

## Labels

tests, backend

## Dependencies

None
