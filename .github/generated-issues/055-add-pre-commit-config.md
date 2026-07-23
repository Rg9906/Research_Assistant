# Add a pre-commit config

## Background

Ruff (Python) and oxlint/tsc (frontend) only run in CI today — there is no
`.pre-commit-config.yaml`. A contributor's first signal that their code
fails lint is a red CI check after pushing, rather than immediate feedback
before committing.

## Why it matters

Catching lint failures before a push (rather than after opening a PR) is a
small but meaningful contributor-experience improvement, and it keeps CI
minutes focused on things a local hook can't catch (cross-platform
behavior, the full test suite) rather than formatting nits.

## Proposed solution

Add `.pre-commit-config.yaml` running `ruff check --fix` and `ruff format`
(if/when formatting is adopted) on Python files, and mention optional setup
(`pre-commit install`) in `CONTRIBUTING.md`. Keep it opt-in — don't make CI
depend on pre-commit being installed locally, since not every contributor
will have it set up.

## Acceptance criteria

- [ ] `.pre-commit-config.yaml` exists and runs ruff
- [ ] `CONTRIBUTING.md` documents `pip install pre-commit && pre-commit install`
      as an optional step
- [ ] Running `pre-commit run --all-files` passes on the current codebase

## Suggested files

- `.pre-commit-config.yaml` (new)
- `CONTRIBUTING.md`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

enhancement, ci, good first issue

## Dependencies

None.
