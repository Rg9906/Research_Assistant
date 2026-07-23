# Add pagination to workspace list endpoints

## Background

`GET /api/workspaces` and `GET /api/workspaces/{id}/papers` in
`src/app/api.py` return every row unconditionally:

```python
@app.get("/api/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces(db: WorkspaceManager = Depends(get_db_manager)):
    workspaces = db.list_workspaces()
    return [WorkspaceResponse(...) for w in workspaces]
```

There's no `limit`/`offset` (or cursor) support at either the API or the
`WorkspaceManager` query layer.

## Why it matters

At today's single-user scale this is invisible. But `ResearchLibrary.tsx`
already renders every workspace as an unpaginated grid, and a user who
actually uses this tool for a semester's worth of papers will eventually
have dozens of workspaces loaded (and rendered) in one request/page. This
is a "grows into a problem" issue rather than an active bug — worth fixing
before it's the thing a new user hits on day 30 of real use.

## Proposed solution

Add optional `limit`/`offset` query parameters to both endpoints, with
sensible defaults (e.g. `limit=50, offset=0`), and thread them into
`WorkspaceManager.list_workspaces`/`get_workspace_papers` as `LIMIT`/
`OFFSET` clauses on the underlying SQL. Keep the default behavior
unchanged for small workspace counts (existing frontend calls with no
params should still get everything up to the default limit).

## Acceptance criteria

- [ ] `GET /api/workspaces?limit=10&offset=0` returns at most 10 rows.
- [ ] `GET /api/workspaces/{id}/papers` supports the same parameters.
- [ ] Defaults preserve current behavior for workspace counts under the
      default limit (no frontend changes required to keep working).
- [ ] Tests cover both the default (no params) and explicit
      limit/offset cases.

## Suggested files

- `src/app/api.py`
- `src/paperpilot/workspace/manager.py`
- `tests/test_workspace.py`, `tests/test_api.py`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

`enhancement`, `backend`, `performance`

## Dependencies

None.
