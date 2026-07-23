# Add endpoint tests for `/api/workspaces` CRUD (list/create/delete)

## Background

`tests/test_api.py` only exercises `/api/workspaces/{id}/chat` and the
summary endpoints — `list_workspaces` (`src/app/api.py:175`),
`create_workspace` (`:186`), and `delete_workspace` (`:194`) have zero
endpoint-level tests. The underlying `WorkspaceManager` methods are unit
tested in `test_workspace.py`, but nothing verifies the FastAPI wiring
itself: status codes, response shapes, the `ValueError` → HTTP 400 mapping
in `create_workspace`, or that `delete_workspace` correctly also clears the
workspace's chat history via `chat_store.set(workspace_id, [])`.

## Why it matters

These are three of the most basic CRUD operations in the product — the
`ResearchLibrary` page depends on all three. A regression here (e.g. a
broken response model, a dropped status code) would only be caught by
manually clicking through the UI, not by CI.

## Proposed solution

Add a `TestWorkspaceCrud` class to `tests/test_api.py` following the existing
`dependency_overrides` + `TestClient` pattern used for chat/summary tests.
Cover: list returns the seeded workspaces with correct `paper_count`, create
returns 200 with a new `workspace_id`, create with a duplicate/invalid name
returns 400 (matching the `ValueError` branch), delete returns success and
subsequently clears chat history (assert via `WorkspaceChatStore`).

## Acceptance criteria

- [ ] `GET /api/workspaces` is tested for both empty and populated cases
- [ ] `POST /api/workspaces` is tested for the happy path and the 400 error path
- [ ] `DELETE /api/workspaces/{id}` is tested, including that it clears chat history
- [ ] Tests use `dependency_overrides`, not a real database

## Suggested files

- `tests/test_api.py`
- `src/app/api.py` (read-only reference, lines 174-201)

## Difficulty

Easy

## Estimated time

1.5 hours

## Labels

good first issue, tests, backend

## Dependencies

None.
