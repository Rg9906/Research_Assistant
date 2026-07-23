# Bootstrap a frontend test suite (Vitest + React Testing Library)

## Background

The frontend (`frontend/`, React 19 + Vite + TypeScript) has no test runner
configured at all — no Vitest, no Jest, no React Testing Library in
`package.json`, and no `*.test.tsx` files anywhere in `frontend/src/`. CI
(`.github/workflows/lint.yml`) only runs `oxlint` and `tsc -b` for the
frontend, because there's nothing else to run.

## Why it matters

This is the single largest testing gap in the project: the backend has 173+
offline tests; the frontend, a full React app with real state (contexts,
routing, API calls), has zero. A type-checker confirms shapes, not behavior —
none of the frontend bugs already found in this audit (dead click
affordances, a broken deep-link, an unwired delete button) would have been
caught by `tsc` alone.

## Proposed solution

Add Vitest (it integrates directly with the existing Vite config, no
separate bundler needed) plus `@testing-library/react` and
`@testing-library/jest-dom` to `frontend/package.json`. Wire an `npm test`
script, add a CI job (either a new step in `lint.yml` or a new
`frontend-tests.yml`), and land one real smoke test — e.g. `ThemeContext`
correctly toggling the `.dark` class on `<html>`, or `AgentActivityContext`
reflecting an in-flight request — to prove the harness works end-to-end, not
just that it's installed.

## Acceptance criteria

- [ ] Vitest + React Testing Library installed and configured
- [ ] `npm test` runs in CI on every push/PR
- [ ] At least one real, meaningful test passes
- [ ] CONTRIBUTING.md documents how to run frontend tests locally

## Suggested files

- `frontend/package.json`
- `frontend/vite.config.ts` (or a new `vitest.config.ts`)
- `.github/workflows/lint.yml`
- `CONTRIBUTING.md`

## Difficulty

Medium

## Estimated time

1 day

## Labels

tests, frontend, ci

## Dependencies

Blocks every future frontend-component test issue (including deeper
regression coverage for #026, #029, #030, #031, #032).
