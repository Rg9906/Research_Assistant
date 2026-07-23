# Add per-IP rate limiting middleware

## Background

Same source as #018: SECURITY.md and ROADMAP.md both name rate limiting as
required "ops hardening" before any non-local deployment. Today, nothing
in `src/app/api.py` limits request rate per client — a single caller could
issue unlimited `/api/search` (hitting the already-rate-limited Semantic
Scholar quota indirectly) or `/api/workspaces/{id}/chat` (each call costs
1–3 real LLM requests) calls back-to-back.

## Why it matters

Beyond abuse prevention, this protects the app's own external quotas: the
Semantic Scholar API key has a real per-key rate limit
(`semantic_scholar_rate_limit_rps`), and every LLM provider has its own
per-minute token/request quota (CLAUDE.md §5's token-budgeting notes make
clear how easily these get exhausted). An unthrottled client hammering
`/api/search` or `/api/workspaces/{id}/chat` can burn through a shared
quota on behalf of every other user of the same deployment.

## Proposed solution

Add a lightweight rate-limiting middleware (e.g. using `slowapi`, the
common FastAPI-oriented wrapper around `limits`, or a small custom
in-memory token-bucket keyed by client IP — matching the project's
existing `RateLimiter` pattern in `search/rate_limit.py`, which could
plausibly be reused/generalized here). Apply sensible per-endpoint limits:
tighter on `/api/papers/process` and `/api/workspaces/{id}/chat` (expensive,
LLM-backed) than on read-only endpoints like `GET /api/workspaces`.

Make limits configurable via `Settings` so a single trusted local user can
disable this entirely (default: generous or disabled for localhost, as
today).

## Acceptance criteria

- [ ] Configurable per-endpoint (or global) request-rate limits.
- [ ] Exceeding a limit returns `429` with a `Retry-After` header.
- [ ] Default configuration does not disrupt normal local single-user use.
- [ ] Documented in `.env.example` and `SECURITY.md`.
- [ ] Covered by a test that exceeds the configured limit and asserts
      `429`.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/config.py`
- `src/paperpilot/search/rate_limit.py` (candidate for reuse/generalization)
- `SECURITY.md`, `.env.example`

## Difficulty

Medium

## Estimated time

1 day

## Labels

`security`, `backend`, `enhancement`

## Dependencies

None. Related to #018 (auth).
