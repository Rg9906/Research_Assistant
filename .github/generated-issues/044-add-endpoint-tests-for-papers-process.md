# Add endpoint tests for `/api/papers/process`

## Background

`POST /api/papers/process` (`src/app/api.py:354`, `process_paper`) has no
endpoint-level test. This is the single most consequential endpoint in the
backend: CLAUDE.md §7 documents, as a historically resolved P0 bug, that
`process_paper` used to write a paper into the workspace database *before*
indexing it, so a failed index left a permanently unchattable paper stuck in
a workspace. That fix (index-first, DB-write-only-on-success) is currently
guarded only by tests at the `PaperSessionManager` level — nothing pins the
ordering at the API layer itself, where the original bug actually lived.

## Why it matters

This is exactly the kind of regression that's invisible until a real user
hits it: a refactor of `process_paper` that reorders the DB write and the
indexing call would pass every existing test and silently reintroduce a
fixed P0 bug.

## Proposed solution

Add a test that mocks `PaperSessionManager.get_or_create_session` to raise
(simulating an indexing failure) and asserts the workspace/paper is **not**
persisted to the database afterward. Add a companion happy-path test
confirming a successful call does persist to the DB. Use
`dependency_overrides`, not real PDF downloads.

## Acceptance criteria

- [ ] A simulated indexing failure results in no DB write (workspace/paper
      absent afterward)
- [ ] A successful call persists the workspace and paper as expected
- [ ] Test explicitly references CLAUDE.md §7's documented incident in a
      comment, so a future reader understands why this ordering matters

## Suggested files

- `tests/test_api.py`
- `src/app/api.py:354` onward

## Difficulty

Medium

## Estimated time

3 hours

## Labels

tests, backend

## Dependencies

None.
