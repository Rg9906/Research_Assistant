---
title: "Quick mitigation: return from /api/papers/process before indexing finishes"
labels: ['backend', 'performance']
difficulty: Medium
estimate: "1 day"
category: "⚡ Performance"
---

# Quick mitigation: return from /api/papers/process before indexing finishes

**Category:** ⚡ Performance

## Background

`process_paper` (`src/app/api.py`) calls `session_manager.get_or_create_session(...)` synchronously inline in the request handler. On a cache miss this downloads the PDF, parses it with PyMuPDF, chunks it, and embeds every chunk — all before the HTTP response is sent. For a long paper this can take well over a minute, during which the request is blocked with zero feedback. This issue is the **small, fast mitigation**; issue #46 tracks the proper long-term background-job/worker-pool architecture. Ship this first — it's a same-week fix that immediately improves the worst UX moment in the product, without waiting on the bigger design.

## Why it matters

This is the single biggest responsiveness problem a real user hits: clicking "process this paper" in the UI currently means staring at a spinner for up to a minute or more with zero feedback on progress, and a dropped connection during that window loses the work entirely. A minimal fix now is worth more than a perfect fix later.

## Proposed solution

Use FastAPI's built-in `BackgroundTasks` (no new infrastructure) to kick off `get_or_create_session` after returning a quick "accepted" response, and add a simple in-memory status flag (`pending` / `ready` / `failed`) keyed by `paper_id` that the frontend can poll. This is intentionally the minimal version — issue #46 replaces the in-memory status/worker with a real, restart-safe job queue once the product has enough usage to justify it.

## Acceptance Criteria

- [ ] `/api/papers/process` returns immediately (HTTP 202-style) instead of blocking until indexing finishes
- [ ] A simple status check (new endpoint or field on an existing one) reports `pending`/`ready`/`failed` for a paper being processed
- [ ] The frontend shows a real "indexing…" state instead of a blocked network request
- [ ] A failed indexing job surfaces its error the same way the current synchronous path does
- [ ] Explicitly scoped as the minimal fix — no new job-queue infrastructure (that's issue #46)

## Suggested files

`src/app/api.py`, `src/paperpilot/services/paper_chat/session.py`, `frontend/src/components/PaperSummary.tsx`

## Difficulty

Medium

## Estimated time

1 day

## Labels

backend, performance

## Dependencies

None — this ships before, and independently of, #46 (the full job-queue version)
