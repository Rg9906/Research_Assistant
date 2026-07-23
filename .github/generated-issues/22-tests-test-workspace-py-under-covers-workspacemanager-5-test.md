---
title: "`tests/test_workspace.py` under-covers `WorkspaceManager` (5 tests for 8+ public methods)"
labels: ['good first issue', 'tests', 'backend']
difficulty: Easy
estimate: "2 hours"
category: "🧪 Testing"
---

# `tests/test_workspace.py` under-covers `WorkspaceManager` (5 tests for 8+ public methods)

**Category:** 🧪 Testing

## Background

`WorkspaceManager` (`src/paperpilot/workspace/manager.py`) exposes `create_workspace`, `delete_workspace`, `list_workspaces`, `add_paper_to_workspace`, `get_workspace_papers`, `get_paper_by_id`, `get_chunks_for_workspace`, and `update_paper_metadata` — eight public methods backed by real SQLite schema and foreign-key cascade behavior. `tests/test_workspace.py` currently has five test functions, and it's not evident from a quick read that `update_paper_metadata`, cascade-on-delete, or "same paper added to two workspaces" are covered at all.

## Why it matters

This module owns the only source of truth for which papers belong to which workspace — a silent regression here (e.g. a broken cascade delete, or a broken update) corrupts user data with no test to catch it before release.

## Proposed solution

Add tests for: `update_paper_metadata` actually persisting a change and being readable back via `get_paper_by_id`; `delete_workspace` cascading to remove `workspace_papers` rows (but not the `papers` row itself, since a paper can belong to multiple workspaces); adding the same paper to two different workspaces and confirming `get_workspace_papers` returns it correctly for both.

## Acceptance Criteria

- [ ] A test covers `update_paper_metadata` round-tripping a change
- [ ] A test covers cascade-delete behavior for `workspace_papers` on `delete_workspace`
- [ ] A test covers one paper belonging to two workspaces simultaneously
- [ ] All new tests are fully offline, using `tmp_path` for the SQLite file per existing convention

## Suggested files

`tests/test_workspace.py`

## Difficulty

Easy

## Estimated time

2 hours

## Labels

good first issue, tests, backend

## Dependencies

None
