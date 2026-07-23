# Replace `response_model=List[Any]` with a typed model

## Background

`GET /api/workspaces/{workspace_id}/papers` in `src/app/api.py` is declared:

```python
@app.get("/api/workspaces/{workspace_id}/papers", response_model=List[Any])
def list_workspace_papers(workspace_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    papers = db.get_workspace_papers(workspace_id)
    return [p.model_dump() for p in papers]
```

`List[Any]` opts this endpoint out of FastAPI/Pydantic's response
validation and out of the auto-generated OpenAPI schema (`/docs` shows this
endpoint returning an untyped array), even though the actual return type is
always `list[PaperMetadata]` (the same model already defined in
`paperpilot/core/models.py` and already used elsewhere in this file).

## Why it matters

This is the one endpoint in the file that doesn't follow the project's own
"Pydantic as the contract layer" convention (CLAUDE.md §6). It's a small
thing, but it's exactly the kind of inconsistency a new contributor
copy-pastes forward into the next endpoint they add, and it silently
degrades the generated API docs for the frontend's own consumption.

## Proposed solution

```python
@app.get("/api/workspaces/{workspace_id}/papers", response_model=List[PaperMetadata])
def list_workspace_papers(workspace_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    return db.get_workspace_papers(workspace_id)
```

`PaperMetadata` is already imported in this file. FastAPI will serialize
the Pydantic models directly — the explicit `.model_dump()` becomes
unnecessary.

## Acceptance criteria

- [ ] The endpoint's `response_model` is `List[PaperMetadata]`.
- [ ] `/docs` (Swagger UI) shows the real schema for this endpoint instead
      of an untyped array.
- [ ] Existing frontend behavior is unchanged (the JSON shape serializes
      the same way either way — verify with the existing `fetchWorkspacePapers`
      consumer in `frontend/src/api/client.ts`).
- [ ] Add or update a test asserting the response matches the
      `PaperMetadata` shape.

## Suggested files

- `src/app/api.py`

## Difficulty

Beginner

## Estimated time

30 minutes

## Labels

`good first issue`, `backend`, `refactor`

## Dependencies

None.
