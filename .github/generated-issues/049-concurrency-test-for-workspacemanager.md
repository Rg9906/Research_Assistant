# Add a concurrency test for `WorkspaceManager`

## Background

Issue #004 proposes adding WAL mode and a `busy_timeout` to
`WorkspaceManager`'s SQLite connections to handle concurrent writes safely
(multiple workspace-chat requests or paper-processing calls hitting the DB
at once). Without a concurrency test, there's no way to verify the fix
actually prevents `database is locked` errors under load, as opposed to just
looking correct.

## Why it matters

SQLite concurrency bugs are notoriously easy to "fix" in a way that looks
right in a single-threaded test suite and still fails under real concurrent
access — the only way to be confident is to actually exercise it
concurrently.

## Proposed solution

Once #004 lands, add a test that spawns several threads (e.g. via
`concurrent.futures.ThreadPoolExecutor`) each performing a write
(`create_workspace`, `add_paper_to_workspace`, etc.) against the same
`tmp_path`-backed database, and asserts all writes succeed with no
`sqlite3.OperationalError`.

## Acceptance criteria

- [ ] Test fails against the pre-#004 connection settings under enough
      concurrent load to reproduce lock contention
- [ ] Test passes reliably after #004's WAL mode / busy_timeout change
- [ ] Uses `tmp_path`, no shared state across test runs

## Suggested files

- `tests/test_workspace.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

tests, backend

## Dependencies

Depends on #004 landing first.
