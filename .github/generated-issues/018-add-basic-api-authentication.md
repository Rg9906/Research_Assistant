# Add basic API authentication for non-localhost deployments

## Background

SECURITY.md is explicit about this: *"PaperPilot AI is currently designed
to run locally on `localhost` and has no authentication layer ... If you
deploy it beyond a trusted local machine, you are responsible for adding
authentication, rate limiting, and network controls."* CLAUDE.md §11 and
ROADMAP.md both list authentication as the first item under "ops
hardening" for any non-local deployment. There is currently no auth
mechanism anywhere in `src/app/api.py`.

## Why it matters

This is the single largest blocker to anyone running PaperPilot AI as
anything other than a single-user local tool — a lab wanting to share one
instance across a research group, or a small team, currently has no way to
gate access at all. It's explicitly named as tracked, known work in both
SECURITY.md and the roadmap; this issue turns that acknowledgment into a
scoped, mergeable task.

## Proposed solution

Given the project's current scale and local-first design, a full
multi-user identity system (OAuth, user accounts, per-user workspaces) is
likely more than this project needs today. A reasonable, incremental first
step:
1. Support a single shared API key/bearer token, configured via
   `Settings` (e.g. `api_auth_token: str = ""`), checked via a FastAPI
   dependency applied to every route except a health check.
2. When unset (the default, matching today's local-only behavior), no
   auth is required — this must not break the documented local dev
   workflow.
3. When set, every request must present a matching `Authorization: Bearer
   <token>` header, or receive `401`.
4. Document the setting in `.env.example` and `SECURITY.md`, and note it
   as the minimum bar before exposing the API beyond localhost.

Leave room for a maintainer to later replace this with real per-user auth
if the project grows multi-tenant ambitions — this issue is scoped to
"close the documented gap with the simplest correct mechanism," not to
design a full identity system.

## Acceptance criteria

- [ ] With `api_auth_token` unset, all existing behavior is unchanged (no
      auth required) — the default local-dev experience does not regress.
- [ ] With `api_auth_token` set, every API route requires a matching
      bearer token, returning `401` otherwise.
- [ ] The frontend can be configured to send the token (e.g. via a Vite
      env var), so a deployed instance with auth enabled still works
      end-to-end.
- [ ] Documented in `.env.example`, `SECURITY.md`, and README's deployment
      guidance.
- [ ] Covered by tests for both the auth-disabled and auth-enabled paths.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/config.py`
- `SECURITY.md`, `.env.example`
- `frontend/src/api/client.ts`

## Difficulty

Hard

## Estimated time

2 days

## Labels

`security`, `backend`, `enhancement`

## Dependencies

None. Related to #019 (rate limiting) — both matter most together for a
non-local deployment, but neither blocks the other.
