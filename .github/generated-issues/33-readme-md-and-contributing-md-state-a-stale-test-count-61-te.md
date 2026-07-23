---
title: "README.md and CONTRIBUTING.md state a stale test count ("61 tests") that's far below the real suite size"
labels: ['good first issue', 'documentation']
difficulty: Beginner
estimate: "15 min"
category: "📚 Documentation"
---

# README.md and CONTRIBUTING.md state a stale test count ("61 tests") that's far below the real suite size

**Category:** 📚 Documentation

## Background

README.md's Quick Start step 4 and CONTRIBUTING.md's "Running tests and linters" section both say "61 tests run fully offline... A further 9 tests in tests/test_embedder.py...". CLAUDE.md §10 (the file that's kept in sync with the code, per its own stated policy) currently says "173 tests pass fully offline (182 collected total)". README/CONTRIBUTING were not updated when the suite grew.

## Why it matters

A stale, understated test count is a small thing that nonetheless undersells the project's actual test rigor to exactly the audience (prospective contributors evaluating whether to invest time here) this whole effort is meant to attract. It's also a trivial "docs are out of sync with code" bug of the kind CLAUDE.md's own header explicitly warns against.

## Proposed solution

Update the test counts in both README.md and CONTRIBUTING.md to match CLAUDE.md §10's current numbers, and add a one-line reminder in CLAUDE.md's own "keep in sync" guidance to update all three files together when the suite size changes meaningfully.

## Acceptance Criteria

- [ ] README.md and CONTRIBUTING.md test counts match CLAUDE.md §10
- [ ] A note (CLAUDE.md or CONTRIBUTING.md) reminds future contributors to update all three when the count changes

## Suggested files

`README.md`, `CONTRIBUTING.md`

## Difficulty

Beginner

## Estimated time

15 min

## Labels

good first issue, documentation

## Dependencies

None
