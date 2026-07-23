# Background/async PDF indexing so `/api/papers/process` doesn't block a worker thread

## Background

`POST /api/papers/process` runs the entire PDF download → parse → chunk →
embed → persist pipeline (`PaperSessionManager.get_or_create_session`)
synchronously within the request/response cycle. This is already called
out as a known, tracked concern in ROADMAP.md and CLAUDE.md §11 ("Ops
hardening ... background indexing for slow PDF processing (still
synchronous in the request, and now slower since chat does up to 3 LLM
round-trips)"). This issue operationalizes that roadmap line into a
concrete, scoped task.

## Why it matters

FastAPI runs sync `def` endpoints in a bounded thread pool. A slow PDF
(large file, slow publisher server, cold-start embedding model load) ties
up one of those threads for the full duration — potentially tens of
seconds to minutes on a cold machine (CLAUDE.md notes multi-minute model
loads are possible). Under any concurrent load, this is the endpoint most
likely to exhaust the thread pool and make unrelated requests (search,
chat on already-indexed papers) appear to hang.

## Proposed solution

Introduce a job-based flow:
1. `POST /api/papers/process` enqueues the indexing work (a background
   task via FastAPI's `BackgroundTasks`, or a simple in-process job queue
   given the project's existing "process-local" caching conventions — see
   CLAUDE.md §6 on `lru_cache` singletons) and returns immediately with a
   job/paper status of `"processing"`.
2. A new `GET /api/papers/{paper_id}/status` (or reuse `GET /api/papers/
   {paper_id}` from #011 with a `status` field) lets the frontend poll
   until indexing completes or fails.
3. `PaperSummary.tsx`'s existing "Preparing Paper..." overlay (it already
   has loading-message UI for this) polls the new status endpoint instead
   of awaiting one long request.

Keep this scoped to the existing single-process deployment model — a full
task-queue system (Celery/RQ + Redis) is out of scope unless a maintainer
decides the project needs multi-process scaling; `BackgroundTasks` or a
simple `ThreadPoolExecutor`-backed queue is sufficient for the documented
local/small-deployment use case.

## Acceptance criteria

- [ ] `POST /api/papers/process` returns promptly (e.g. under 1 second)
      regardless of PDF size, with the workspace_id and a `processing`
      status.
- [ ] A status endpoint reports `processing`, `ready`, or `failed` (with
      the existing sanitized error message on failure).
- [ ] The frontend polls and transitions its existing loading overlay to
      the ready/error state without a full-page reload.
- [ ] Concurrent search/chat requests are not affected by an in-progress
      indexing job.
- [ ] Covered by tests exercising the async flow with a stubbed
      `PaperSessionManager`.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/services/paper_chat/session.py`
- `frontend/src/components/PaperSummary.tsx`
- `frontend/src/api/client.ts`

## Difficulty

Hard

## Estimated time

3 days

## Labels

`enhancement`, `backend`, `performance`, `frontend`

## Dependencies

None, but pairs well with #011 if status is folded into the paper-by-id
response.
