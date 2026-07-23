---
title: "`PaperSessionManager._active_sessions` grows without bound for the life of the process"
labels: ['backend', 'bug', 'performance']
difficulty: Medium
estimate: "3 hours"
category: "🐛 Bug"
---

# `PaperSessionManager._active_sessions` grows without bound for the life of the process

**Category:** 🐛 Bug

## Background

`PaperSessionManager` (`src/paperpilot/services/paper_chat/session.py`) caches every `PaperSession` it builds in `self._active_sessions: Dict[str, PaperSession]` and never evicts an entry. Each `PaperSession` holds a live `VectorStoreIndex` with all of that paper's embedded chunks resident in memory. On a server that processes many papers over time (exactly what an active multi-user or long-uptime deployment does), memory usage grows monotonically until the process is restarted.

## Why it matters

This is the kind of bug that's invisible in local dev (a handful of papers, short-lived process) and only shows up as an OOM in a real deployment — precisely the gap between "works on my machine" and "runs in production" that this project's SECURITY.md/ROADMAP.md already flag as unaddressed ops hardening.

## Proposed solution

Add a bounded LRU eviction policy to `_active_sessions` (e.g. `functools.lru_cache`-style or a small manual OrderedDict-based LRU, evicting the least-recently-used `PaperSession` once a configurable `max_active_sessions` is exceeded). Evicting a session should not delete its on-disk index — `get_or_create_session` already reloads from disk on a cache miss via the fingerprint check.

## Acceptance Criteria

- [ ] A new `Settings.max_active_sessions` (or similar) config knob exists with a sensible default
- [ ] `PaperSessionManager` evicts the least-recently-used session once the limit is exceeded
- [ ] A test creates more sessions than the limit and asserts the manager's in-memory session count never exceeds it
- [ ] Re-requesting an evicted paper still works (reloads from the on-disk index, per existing fingerprint logic)

## Suggested files

`src/paperpilot/services/paper_chat/session.py`, `src/paperpilot/config.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

backend, bug, performance

## Dependencies

None
