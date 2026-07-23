---
title: "Move PDF processing off the request thread into a background job with pollable status"
labels: ['feature', 'backend', 'enhancement']
difficulty: Hard
estimate: "3 days"
category: "🚀 Feature"
---

# Move PDF processing off the request thread into a background job with pollable status

**Category:** 🚀 Feature

## Background

Issue #11 ships a minimal fix (FastAPI `BackgroundTasks` + an in-memory status flag) to stop the request from blocking. That's enough for a single-user local instance, but it doesn't survive a process restart, doesn't support multiple worker processes, and has no retry/backoff for a failed job. This issue is the **durable, production-grade follow-up**: replace the minimal version with a real background-job abstraction once actual multi-user usage justifies the investment.

## Why it matters

This is the foundational piece of ROADMAP.md's #1 priority ("background indexing for slow PDF processing"), and is what actually unblocks a real multi-instance/production deployment rather than just improving the local-dev feel (which #11 already covers).

## Proposed solution

Introduce a real task-queue abstraction (e.g. `arq`, Celery, or an equivalent), backed by Redis or the existing SQLite DB for job state, replacing the in-memory status flag from #11. Jobs and their status survive a backend restart and work correctly across multiple worker processes.

## Acceptance Criteria

- [ ] Paper-processing jobs are durable — they survive a backend restart and are visible across multiple worker processes
- [ ] A status-check path exists for the frontend to poll until `ready` or `failed`, replacing #11's in-memory version
- [ ] Failed jobs get a retry/backoff policy instead of silently staying failed
- [ ] Existing synchronous callers/tests are updated to the new async contract

## Suggested files

`src/app/api.py`, `src/paperpilot/services/paper_chat/session.py`, `frontend/src/components/PaperSummary.tsx`

## Difficulty

Hard

## Estimated time

3 days

## Labels

feature, backend, enhancement

## Dependencies

Builds on #11 (the minimal `BackgroundTasks`-based mitigation) — do that first; this issue replaces its in-memory status tracking with a durable job queue once usage justifies it.
