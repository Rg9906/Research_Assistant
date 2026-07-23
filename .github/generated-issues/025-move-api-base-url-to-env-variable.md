# Move `API_BASE_URL` to a Vite environment variable

## Background

`frontend/src/api/client.ts` hardcodes the backend origin:

```ts
export const API_BASE_URL = 'http://localhost:8000/api';
```

CLAUDE.md itself flags this as a known characteristic of the current setup
("base URL is hardcoded to `http://localhost:8000/api`"). Every API call in
the frontend goes through this single constant, so this is genuinely a
one-line fix with a disproportionate payoff.

## Why it matters

This is the single biggest blocker to running the frontend against
anything other than a locally-running backend on port 8000 — a deployed
backend, a Docker Compose setup with a different service hostname, or even
just a different local port, all currently require editing source code.
It's also the most common "first PR" style fix in any frontend repo, and a
good, safe onboarding task.

## Proposed solution

```ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
```

Add a `frontend/.env.example` (or extend the root one, if the project
prefers a single `.env.example`) documenting `VITE_API_BASE_URL`, and note
it in `CONTRIBUTING.md`'s frontend setup section.

## Acceptance criteria

- [ ] `API_BASE_URL` reads from `VITE_API_BASE_URL` when set, falling back
      to today's hardcoded default otherwise (no behavior change for
      existing contributors who don't set it).
- [ ] Documented in a `frontend/.env.example` and `CONTRIBUTING.md`.
- [ ] `npm run build` and `npx tsc -b` remain clean.

## Suggested files

- `frontend/src/api/client.ts`
- `frontend/.env.example` (new)
- `CONTRIBUTING.md`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `frontend`

## Dependencies

None.
