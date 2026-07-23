# Handle errors after successful indexing in `process_paper`

## Background

`POST /api/papers/process` (`src/app/api.py`) wraps the indexing step in a
try/except that logs via `logger.exception` and returns a sanitized error
(the project's documented pattern — see CLAUDE.md's "API handlers used to
leak `str(e)`" resolved issue). But the code that runs *after* a successful
index — creating/finding the workspace and calling
`db.add_paper_to_workspace(...)` — has no such wrapping:

```python
workspace_name = f"Paper: {request.title}"[:50]
try:
    workspace_id = db.create_workspace(workspace_name)
except ValueError:
    ...
    else:
        raise _fail(500, "Failed to create or find workspace", ValueError(workspace_name))

db.add_paper_to_workspace(workspace_id, paper_meta, chunks=[])  # <-- unguarded

return {"workspace_id": str(workspace_id)}
```

If `add_paper_to_workspace` raises (a SQLite error, a disk-full condition,
etc.), the exception propagates unhandled — it bypasses `_fail`'s
`logger.exception` + sanitized-message pattern that every other failure
path in this file follows.

## Why it matters

Consistency: this project explicitly fixed "API handlers leaking `str(e)`"
as a P0/P1 issue (CLAUDE.md §7) and standardized on `_fail()` everywhere.
This one code path was missed, so a DB failure here produces FastAPI's
default unhandled-exception response instead of the sanitized message the
rest of the API guarantees, and — more importantly — it isn't logged via
`logger.exception`, so a maintainer debugging "papers keep failing to save
after a successful index" would have no server-side log entry to go on.

## Proposed solution

Wrap the workspace-creation/attach step in the same try/except + `_fail(...)`
pattern used elsewhere in this file:

```python
try:
    workspace_name = f"Paper: {request.title}"[:50]
    try:
        workspace_id = db.create_workspace(workspace_name)
    except ValueError:
        ...
    db.add_paper_to_workspace(workspace_id, paper_meta, chunks=[])
except Exception as e:
    raise _fail(500, f"Indexed '{request.title}' but failed to save it to a workspace", e)
```

## Acceptance criteria

- [ ] A failure in `create_workspace`/`add_paper_to_workspace` after a
      successful index is caught, logged via `logger.exception`, and
      returns a sanitized `HTTPException` consistent with the rest of the
      endpoint.
- [ ] A test simulates `add_paper_to_workspace` raising and asserts a 500
      with a sanitized message (no raw exception text in the response
      body).

## Suggested files

- `src/app/api.py`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

`bug`, `backend`

## Dependencies

None.
