---
title: "Persist `WorkspaceChatStore` to SQLite so conversation memory survives a restart"
labels: ['feature', 'backend', 'enhancement']
difficulty: Hard
estimate: "2 days"
category: "🚀 Feature"
---

# Persist `WorkspaceChatStore` to SQLite so conversation memory survives a restart

**Category:** 🚀 Feature

## Background

`WorkspaceChatStore` (`src/app/utils.py`) is an in-memory `Dict[str, List[ChatMessage]]` — CLAUDE.md §6 explicitly notes "history does not survive a server restart. Persisting it to the workspace DB is future work if cross-restart memory is needed," and ROADMAP.md lists "Long-term memory" under Planned/future.

## Why it matters

Losing every conversation on every deploy/restart is a real usability gap for anyone running this beyond a single local dev session — restarting the backend to pick up a config change currently means every open chat silently forgets everything discussed so far.

## Proposed solution

Add a `chat_history` table to the existing `workspace.db` (via `WorkspaceManager`, keeping one schema owner per CLAUDE.md §9's "prefer extending existing modules" guidance), and have `WorkspaceChatStore` read through to it on `get()` (with an in-memory cache for hot paths) and write through on `set()`.

## Acceptance Criteria

- [ ] Chat history for a workspace survives a full backend restart
- [ ] The existing in-memory fast path is preserved for hot reads within a single process lifetime
- [ ] A migration path exists for `data/workspace.db` (new table, no destructive change to existing tables)
- [ ] Tests cover a simulated "restart" (new `WorkspaceChatStore` instance backed by the same DB file) retaining history

## Suggested files

`src/paperpilot/workspace/manager.py`, `src/app/utils.py`, `tests/test_workspace.py`

## Difficulty

Hard

## Estimated time

2 days

## Labels

feature, backend, enhancement

## Dependencies

None
