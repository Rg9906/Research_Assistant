---
title: "Add a regression test for the `/api/search` `limit` bound once it's added"
labels: ['good first issue', 'tests', 'backend']
difficulty: Beginner
estimate: "30 min"
category: "🧪 Testing"
---

# Add a regression test for the `/api/search` `limit` bound once it's added

**Category:** 🧪 Testing

## Background

This is the test-side follow-up to the `SearchQuery.limit` bug (see the dedicated Bug issue): once a ceiling is added, nothing currently guards against someone quietly loosening or removing it in a future PR.

## Why it matters

A validation boundary with no test protecting it tends to get "quietly fixed" back to unbounded the first time someone hits the ceiling and doesn't understand why it's there.

## Proposed solution

Add parametrized tests to `tests/test_api.py` covering: the max allowed limit (200 OK), one above the max (422), zero (422), and a negative value (422).

## Acceptance Criteria

- [ ] Tests exist for the boundary, one-above-boundary, zero, and negative `limit` values
- [ ] Tests fail if the bound from the Bug issue is ever loosened without updating this test

## Suggested files

`tests/test_api.py`

## Difficulty

Beginner

## Estimated time

30 min

## Labels

good first issue, tests, backend

## Dependencies

Depends on #1 (bound `SearchQuery.limit`)
