# Fix workspace-name collision when two papers share a 50-character title prefix

## Background

`POST /api/papers/process` (`src/app/api.py`) derives a workspace name from
the paper title, truncated to 50 characters:

```python
workspace_name = f"Paper: {request.title}"[:50]
...
try:
    workspace_id = db.create_workspace(workspace_name)
except ValueError:
    workspaces = db.list_workspaces()
    for w in workspaces:
        if w["name"] == workspace_name:
            workspace_id = w["workspace_id"]
            break
    else:
        raise _fail(500, "Failed to create or find workspace", ValueError(workspace_name))
```

`workspaces.name` is `UNIQUE NOT NULL` (`workspace/manager.py`), so
`create_workspace` raises `ValueError` on a name collision, and the handler
falls back to reusing whatever *existing* workspace has that exact name.

If two **different** papers happen to share the same first ~43 characters
of title (common for papers in a series, revisions, or papers with long
shared prefixes like conference proceedings titles), processing the second
paper silently attaches it to the first paper's workspace instead of
creating its own.

## Why it matters

This is a correctness bug with a confusing failure mode: a user processes
Paper B expecting a fresh chat session, and instead gets dropped into Paper
A's existing workspace — Paper B's chat is now grounded in Paper A's index
too (since workspace chat fans out across every paper in the workspace),
and the returned `workspace_id` refers to a workspace whose displayed name
doesn't match Paper B at all. It's silent — no error, no log line
distinguishing "created" from "reused because of a truncated-name clash"
vs. "reused because the user genuinely re-processed the same paper."

## Proposed solution

Don't derive workspace identity from a truncated display string. Options,
roughly in order of preference:

1. Key the per-paper workspace lookup by `paper_id` instead of by name:
   check whether a workspace already contains this exact `paper_id` (via
   `db.get_workspace_papers`/a new small helper) before creating one, and
   only fall back to a fresh `create_workspace(...)` with a name that is
   guaranteed unique (e.g. append a short suffix of the paper's UUID when
   truncating, or drop the `UNIQUE` constraint on `workspaces.name`
   entirely if display names were never meant to be an identity key).
2. At minimum, distinguish "this is the same paper being re-processed"
   (intentional reuse) from "this is a different paper whose name
   truncated to a collision" (bug) — log a warning in the second case
   rather than silently reusing the wrong workspace.

## Acceptance criteria

- [ ] Processing two different papers whose titles share the same
      50-character prefix produces two distinct workspaces.
- [ ] Re-processing the *same* paper still returns its existing workspace
      (no duplicate workspaces for the same paper).
- [ ] A regression test exercises the collision case explicitly (see issue
      #048, which depends on this fix).

## Suggested files

- `src/app/api.py` (`process_paper`)
- `src/paperpilot/workspace/manager.py` (possibly a new
  `get_workspace_for_paper` helper, or relaxing the `name` uniqueness
  constraint)

## Difficulty

Medium

## Estimated time

2 hours

## Labels

`bug`, `backend`

## Dependencies

Blocks #048 (regression test).
