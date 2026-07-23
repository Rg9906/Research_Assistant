---
title: "Auto-created single-paper workspace names can collide between two different papers"
labels: ['backend', 'bug']
difficulty: Medium
estimate: "2 hours"
category: "🐛 Bug"
---

# Auto-created single-paper workspace names can collide between two different papers

**Category:** 🐛 Bug

## Background

`process_paper` in `src/app/api.py` builds a workspace name as `f"Paper: {request.title}"[:50]` and, on a `ValueError` from `create_workspace` (name already exists), looks up *any* workspace with that exact name and reuses it: `db.add_paper_to_workspace(workspace_id, paper_meta, chunks=[])`. Two unrelated papers whose titles are identical in their first ~40 characters (a common pattern for papers in the same series, or papers whose titles are simply long) collide on this truncated name and get silently merged into the same workspace, mixing their chat context.

## Why it matters

This is a correctness bug a user would experience as "why is this workspace chatting about a completely different paper?" with no error and no indication anything went wrong.

## Proposed solution

Key the auto-created workspace lookup by `paper_id` (already a stable UUID) instead of by a truncated, human-readable name — e.g. store the paper→workspace mapping directly and query it, rather than name-matching.

## Acceptance Criteria

- [ ] Two papers whose titles share the same first 50 characters no longer land in the same auto-created workspace
- [ ] A regression test in `tests/test_api.py` creates two such papers and asserts they get distinct workspace IDs
- [ ] Existing single-paper workspace naming behavior (display name shown in the UI) is unchanged

## Suggested files

`src/app/api.py::process_paper`, `src/paperpilot/workspace/manager.py`

## Difficulty

Medium

## Estimated time

2 hours

## Labels

backend, bug

## Dependencies

None
