# Add endpoint tests for workspace-papers listing

## Background

`GET /api/workspaces/{workspace_id}/papers` (`src/app/api.py:203`,
`list_workspace_papers`) has no test in `tests/test_api.py`. It's also the
endpoint whose `response_model=List[Any]` is flagged separately in issue
#007 — testing it now (against the current untyped shape) gives that
refactor a safety net, and testing it again after #007 lands confirms the
new typed model didn't silently change the response shape the frontend
(`ResearchLibrary.tsx`) depends on.

## Why it matters

`ResearchLibrary` and `WorkspaceDetail` both call this endpoint to render a
workspace's paper list. It is untested today, and is about to be touched by
issue #007 — landing a test first means that refactor has something to
break, instead of relying on manual verification.

## Proposed solution

Add a test that creates a workspace, adds a paper (via the `WorkspaceManager`
test fixtures already used elsewhere in `test_api.py`/`test_workspace.py`),
calls the endpoint, and asserts the response contains the expected paper
fields (`paper_id`, `title`, etc.) for both the populated and empty-workspace
cases, plus a 404-equivalent behavior check for an unknown `workspace_id`
(currently returns an empty list rather than 404 — assert today's actual
behavior so a future change is a deliberate decision, not an accident).

## Acceptance criteria

- [ ] A populated workspace returns the expected paper fields
- [ ] An empty/unknown workspace's current behavior is pinned by a test
- [ ] Test survives issue #007's response-model change unmodified (or is
      updated alongside it in the same PR)

## Suggested files

- `tests/test_api.py`
- `src/app/api.py:203-207`

## Difficulty

Easy

## Estimated time

1 hour

## Labels

good first issue, tests, backend

## Dependencies

Pairs with #007 (typed response model) — land this test before or alongside it.
