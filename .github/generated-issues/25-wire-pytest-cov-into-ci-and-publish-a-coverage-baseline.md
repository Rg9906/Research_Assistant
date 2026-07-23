---
title: "Wire `pytest-cov` into CI and publish a coverage baseline"
labels: ['good first issue', 'tests', 'ci']
difficulty: Easy
estimate: "2 hours"
category: "🧪 Testing"
---

# Wire `pytest-cov` into CI and publish a coverage baseline

**Category:** 🧪 Testing

## Background

`pytest-cov>=5.0,<6.0` is a declared dev dependency in `pyproject.toml`, but `.github/workflows/tests.yml` runs plain `pytest tests/ -v --ignore=tests/test_embedder.py` with no `--cov` flag, no coverage threshold, and no artifact/badge. The dependency is installed on every CI run and never used.

## Why it matters

Coverage tracking is one of the most standard signals contributors and reviewers look for on a mature open-source repo, and it directly supports the goal of this whole audit — right now nobody (including the maintainer) has a real number for how well-tested this codebase is beyond "173 tests exist."

## Proposed solution

Add `--cov=paperpilot --cov=app --cov-report=xml --cov-report=term-missing` to the pytest invocation in `tests.yml`, upload the report (e.g. via Codecov's GitHub Action, which is free for open source), and add a coverage badge to README.md. Don't set a hard fail-under threshold yet — establish the baseline first, then open a follow-up issue to raise it once it's known.

## Acceptance Criteria

- [ ] `tests.yml` runs pytest with coverage flags and uploads a report
- [ ] README.md shows a coverage badge
- [ ] The current baseline percentage is recorded (e.g. in a PR description or CHANGELOG entry) so a future issue can set a meaningful `--cov-fail-under` threshold

## Suggested files

`.github/workflows/tests.yml`, `README.md`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, tests, ci

## Dependencies

None
