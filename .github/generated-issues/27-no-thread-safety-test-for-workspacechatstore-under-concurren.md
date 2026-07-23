---
title: "No thread-safety test for `WorkspaceChatStore` under concurrent requests"
labels: ['tests', 'backend']
difficulty: Medium
estimate: "2 hours"
category: "🧪 Testing"
---

# No thread-safety test for `WorkspaceChatStore` under concurrent requests

**Category:** 🧪 Testing

## Background

`WorkspaceChatStore` (`src/app/utils.py`) uses a `threading.Lock` specifically because FastAPI can serve concurrent requests for different workspaces (or, in principle, the same one) on multiple threads. There's no test that actually exercises concurrent `get`/`set` calls from multiple threads to confirm the lock prevents interleaved reads/writes from corrupting a workspace's history list.

## Why it matters

A subtle threading bug here would show up as "my chat history randomly loses messages under load" in production — nearly impossible to reproduce and debug after the fact, but straightforward to guard against with a targeted concurrency test now.

## Proposed solution

Add a test that spawns several threads concurrently calling `.set()` with different histories for the same and different `workspace_id`s, then asserts each workspace's final state is exactly one of the values that was set for it (no torn/interleaved state).

## Acceptance Criteria

- [ ] A test exercises concurrent `get`/`set` from multiple threads against `WorkspaceChatStore`
- [ ] The test asserts no torn/interleaved state for any workspace_id
- [ ] Test is deterministic (no flaky sleep-based timing assumptions)

## Suggested files

`tests/test_api.py` or a new `tests/test_workspace_chat_store.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

tests, backend

## Dependencies

None
