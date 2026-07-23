---
title: "Set up a frontend test framework (Vitest + React Testing Library) — currently zero frontend tests exist"
labels: ['tests', 'frontend', 'ci']
difficulty: Medium
estimate: "1 day"
category: "🧪 Testing"
---

# Set up a frontend test framework (Vitest + React Testing Library) — currently zero frontend tests exist

**Category:** 🧪 Testing

## Background

The frontend (`frontend/`, React 19 + Vite + TypeScript) has no test runner configured at all: no Vitest, no Jest, no React Testing Library in `package.json`, and no `*.test.tsx`/`*.spec.tsx` files anywhere in `frontend/src/`. CI (`lint.yml`) only runs `oxlint` and `tsc -b` for the frontend — there is no frontend test job because there's nothing to run.

## Why it matters

This is the single biggest testing gap in the whole project: the backend has 173+ offline tests and the frontend has zero, despite being a full React app with real state management (contexts, API calls, routing) that a type-checker alone cannot verify behaves correctly.

## Proposed solution

Add Vitest + `@testing-library/react` + `@testing-library/jest-dom` to `frontend/package.json`, wire a `test` script, add it to `lint.yml` (or a new `frontend-tests.yml`) as a CI job, and land one real smoke test (e.g. `AgentActivityContext` reflecting an in-flight request, or `ThemeContext` toggling the `.dark` class) to prove the harness actually works end-to-end, not just that it's installed.

## Acceptance Criteria

- [ ] Vitest + React Testing Library are installed and configured in `frontend/`
- [ ] `npm test` runs in CI on every push/PR
- [ ] At least one real, meaningful test exists and passes
- [ ] README.md/CONTRIBUTING.md document how to run frontend tests locally

## Suggested files

`frontend/package.json`, `frontend/vite.config.ts` (or new `vitest.config.ts`), `.github/workflows/`, `CONTRIBUTING.md`

## Difficulty

Medium

## Estimated time

1 day

## Labels

tests, frontend, ci

## Dependencies

None
