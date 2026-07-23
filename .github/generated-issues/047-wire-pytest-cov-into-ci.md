# Wire `pytest-cov` into CI and publish a coverage baseline

## Background

`pytest-cov>=5.0,<6.0` is a declared dev dependency in `pyproject.toml`, but
`.github/workflows/tests.yml` runs plain `pytest tests/ -v
--ignore=tests/test_embedder.py` — no `--cov` flag, no report, no badge. The
dependency is installed on every CI run and never used.

## Why it matters

Coverage is one of the first signals a prospective contributor or reviewer
looks for on a repo asking for outside PRs. Right now nobody — including the
maintainer — has an actual number for how well-tested this codebase is
beyond "173 tests exist."

## Proposed solution

Add `--cov=paperpilot --cov=app --cov-report=xml --cov-report=term-missing`
to the pytest invocation in `tests.yml`, upload the report via a free
open-source Codecov (or similar) GitHub Action, and add a coverage badge to
`README.md`. Don't set a hard `--cov-fail-under` threshold yet — establish
the baseline first, then open a follow-up issue once the number is known.

## Acceptance criteria

- [ ] `tests.yml` runs pytest with coverage flags and uploads a report
- [ ] `README.md` shows a coverage badge
- [ ] The baseline percentage is recorded (PR description or CHANGELOG) so a
      future issue can set a meaningful threshold

## Suggested files

- `.github/workflows/tests.yml`
- `README.md`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, tests, ci

## Dependencies

None.
