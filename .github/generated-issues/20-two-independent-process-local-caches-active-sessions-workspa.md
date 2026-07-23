---
title: "Two independent process-local caches (`_active_sessions`, `WorkspaceChatStore`) share the same eviction gap with no shared abstraction"
labels: ['refactor', 'backend']
difficulty: Medium
estimate: "1 day"
category: "🏗 Refactor"
---

# Two independent process-local caches (`_active_sessions`, `WorkspaceChatStore`) share the same eviction gap with no shared abstraction

**Category:** 🏗 Refactor

## Background

`PaperSessionManager._active_sessions` (see issue tracking its unbounded growth) and `WorkspaceChatStore` (`src/app/utils.py`) are both hand-rolled, unbounded, process-local `dict`s protecting related but separate concerns (index/session caching vs. conversation memory). Both will eventually need the same shape of fix (bounded size, possibly TTL-based eviction, possibly persistence).

## Why it matters

Solving the eviction problem twice, independently, is exactly the kind of drift CLAUDE.md §6/§7 already warns about elsewhere in the codebase ("the same decision made in two places will drift"). Once issue #4 lands, this is the natural follow-up.

## Proposed solution

Once `PaperSessionManager` gains LRU eviction (see the dedicated issue for that), factor the eviction policy into a small, reusable `BoundedCache` utility and have `WorkspaceChatStore` use the same one, rather than each growing its own bespoke logic.

## Acceptance Criteria

- [ ] A single small reusable bounded-cache utility exists and is used by both `PaperSessionManager` and `WorkspaceChatStore`
- [ ] Existing behavior (cache hit/miss semantics) for both is unchanged apart from the new eviction bound
- [ ] Tests cover eviction for both call sites

## Suggested files

`src/paperpilot/services/paper_chat/session.py`, `src/app/utils.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

refactor, backend

## Dependencies

Depends on #4 (PaperSessionManager LRU eviction)
