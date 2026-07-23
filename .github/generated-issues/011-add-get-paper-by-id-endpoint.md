# Add a `GET /api/papers/{paper_id}` endpoint

## Background

`WorkspaceManager.get_paper_by_id(paper_id: UUID) -> PaperMetadata | None`
already exists (`src/paperpilot/workspace/manager.py`) and is used
internally by `POST /api/papers/{paper_id}/summary/{level_id}` — but there
is no API route that exposes it directly. The frontend has no way to fetch
a single paper's metadata by ID; the only way `PaperSummary.tsx` currently
gets paper data is via React Router's navigation `state`, passed from
`DiscoveryFeed` at click time:

```tsx
navigate(`/paper/${paper.paper_id}`, { state: { paper } });
```//DiscoveryFeed.tsx
```tsx
const paper = state?.paper as Paper | undefined;  // PaperSummary.tsx
if (!paper) { return <p>Paper not found</p>; }
```

## Why it matters

This is the root cause of issue #026 (refreshing or directly opening a
`/paper/:paperId` URL shows "Paper not found" even though the paper is
fully indexed and in the database) — there is currently no backend
endpoint the frontend *could* call to recover the paper's metadata from
just the ID in the URL. Adding this endpoint is a small, self-contained
piece of backend work that unblocks a real, user-visible bug fix.

## Proposed solution

```python
@app.get("/api/papers/{paper_id}", response_model=PaperMetadata)
def get_paper(paper_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    paper = db.get_paper_by_id(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return paper
```

## Acceptance criteria

- [ ] `GET /api/papers/{paper_id}` returns the paper's `PaperMetadata` as
      JSON for a known ID.
- [ ] Returns `404` for an unknown ID.
- [ ] Covered by a test in `tests/test_api.py` (found paper / 404 cases).
- [ ] Documented in the API reference section added by #065.

## Suggested files

- `src/app/api.py`
- `tests/test_api.py`

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

`enhancement`, `backend`, `api`

## Dependencies

Blocks #026 (fixing the frontend deep-link/refresh bug needs this
endpoint to exist first).
