# Add missing docstrings to FastAPI endpoints in `api.py`

## Background

Most endpoints in `src/app/api.py` have no docstring at all
(`list_workspaces`, `create_workspace`, `delete_workspace`,
`list_workspace_papers`, `search_papers`), while a few
(`list_summary_levels`, `summarize_paper`) do. FastAPI uses a route
function's docstring as the description shown in the auto-generated
`/docs` (Swagger UI) page, so this inconsistency means half the API is
undocumented in the interactive docs a new contributor would naturally
reach for first.

## Why it matters

This is a low-effort, high-visibility documentation gap: `/docs` is often
the *first* thing a new contributor opens to understand the API surface,
and right now it's half-empty. It's also inconsistent with the project's
own stated convention (CLAUDE.md §6: "Module and class docstrings explain
*why*, not just *what*").

## Proposed solution

Add a one-to-three-line docstring to each undocumented endpoint function,
following the style already used for `list_summary_levels`/
`summarize_paper` — state what the endpoint does and any non-obvious
behavior (e.g. `delete_workspace` also clears chat history; `create_workspace`
can fail with `400` on a duplicate name).

## Acceptance criteria

- [ ] Every route function in `src/app/api.py` has a docstring.
- [ ] `/docs` shows a description for every endpoint when the server is
      run locally.
- [ ] No behavior change.

## Suggested files

- `src/app/api.py`

## Difficulty

Beginner

## Estimated time

45 minutes

## Labels

`good first issue`, `documentation`, `backend`

## Dependencies

None.
