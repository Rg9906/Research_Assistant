# Add WAL mode + busy_timeout to `WorkspaceManager`'s SQLite connections

## Background

`WorkspaceManager._get_connection()` (`src/paperpilot/workspace/manager.py`)
opens a fresh `sqlite3.connect(self.db_path)` per call and correctly closes
it (already fixed as a documented connection-leak issue — CLAUDE.md §7),
but does not set `PRAGMA journal_mode=WAL` or a `busy_timeout`. SQLite's
default rollback-journal mode locks the entire database file for the
duration of a write transaction, and FastAPI's sync `def` endpoints run in
a thread pool — so two concurrent requests that both touch the DB (e.g. one
processing a paper while another lists workspaces) can race.

## Why it matters

With the default journal mode and no `busy_timeout`, a writer holding the
lock causes any concurrent reader/writer to fail immediately with
`sqlite3.OperationalError: database is locked` rather than waiting briefly
for the lock to clear. This is exactly the kind of intermittent, hard-to-
reproduce error a contributor would file a confusing bug report about. WAL
mode allows concurrent readers alongside a single writer, and a
`busy_timeout` makes transient contention wait-and-retry instead of
erroring outright — cheap insurance for an app whose FastAPI layer already
serves concurrent requests via a thread pool.

## Proposed solution

In `_get_connection()`, immediately after opening the connection:

```python
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")  # ms
```

WAL mode's setting persists in the database file itself after the first
successful call, but setting it on every connection is cheap and
idempotent, so no special first-run handling is needed.

## Acceptance criteria

- [ ] Every connection opened by `WorkspaceManager` runs in WAL mode with a
      non-zero `busy_timeout`.
- [ ] A test opens two connections to the same on-disk DB (via a
      `tmp_path` fixture) and confirms a write on one doesn't immediately
      fail a concurrent read/write on the other within the timeout window
      (see issue #049).
- [ ] No behavior change to any existing test (in-memory/tmp_path DBs still
      work identically).

## Suggested files

- `src/paperpilot/workspace/manager.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

`bug`, `performance`, `backend`

## Dependencies

Recommended before #017 (persisting chat history to SQLite adds more
concurrent writers) and #049 (the concurrency test that verifies this).
