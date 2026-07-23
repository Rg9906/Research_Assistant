---
title: "No rate limiting on any FastAPI endpoint"
labels: ['security', 'backend']
difficulty: Medium
estimate: "1 day"
category: "🔒 Security"
---

# No rate limiting on any FastAPI endpoint

**Category:** 🔒 Security

## Background

Every endpoint in `src/app/api.py` — including `/api/search` (embeds + ranks against two external APIs), `/api/papers/process` (downloads + parses + embeds a whole PDF), and `/api/workspaces/{id}/chat` (up to `1 + rag_max_critique_retries` pairs of LLM calls per request) — has no per-IP or per-client request-rate limiting. SECURITY.md and CLAUDE.md §11 already flag "rate limiting" as unaddressed ops hardening, but there's no concrete tracked issue or starting implementation for it yet.

## Why it matters

Every one of these endpoints costs real money (LLM tokens) or a scarce third-party quota (Semantic Scholar's 1 rps grant, shared process-wide). Without any limiting, a single misbehaving client — or just a retry loop in a buggy frontend build — can exhaust the app's LLM budget or its search quota for every other user.

## Proposed solution

Add a lightweight per-IP rate limiter (e.g. `slowapi`, or a small custom `RateLimiter`-based middleware reusing the pattern already in `search/rate_limit.py`) in front of the expensive endpoints, configurable via `Settings` so self-hosters can tune or disable it.

## Acceptance Criteria

- [ ] The expensive endpoints (`/api/search`, `/api/papers/process`, `/api/workspaces/{id}/chat`, summary generation) return HTTP 429 once a configurable per-IP rate is exceeded
- [ ] The limit is configurable via `Settings` with a sensible default for local/dev use
- [ ] A test asserts the 429 response once the configured limit is exceeded

## Suggested files

`src/app/api.py`, `src/paperpilot/config.py`, `src/paperpilot/search/rate_limit.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

security, backend

## Dependencies

None
