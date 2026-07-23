# Add a `CODEOWNERS` file

## Background

The repository has no `CODEOWNERS` file. With `CONTRIBUTING.md` establishing
a triage workflow (`good first issue`/`help wanted` labels) around a single
maintainer, GitHub's automatic review-request-on-PR feature (which
`CODEOWNERS` enables) currently isn't being used at all.

## Why it matters

As soon as more than one contributor is actively opening PRs, `CODEOWNERS`
means new PRs automatically request the right reviewer instead of relying on
someone noticing an open PR. It's pure configuration — no code risk.

## Proposed solution

Add `.github/CODEOWNERS` mapping top-level areas to the maintainer (and any
future co-maintainers), e.g. `frontend/ @Rg9906`, `src/paperpilot/
@Rg9906`, `src/app/ @Rg9906`, with a catch-all `* @Rg9906`.

## Acceptance criteria

- [ ] `.github/CODEOWNERS` exists and covers `frontend/`, `src/`, and a catch-all
- [ ] A test PR shows the expected reviewer auto-requested

## Suggested files

- `.github/CODEOWNERS` (new)

## Difficulty

Beginner

## Estimated time

15 min

## Labels

good first issue, documentation, ci

## Dependencies

None.
