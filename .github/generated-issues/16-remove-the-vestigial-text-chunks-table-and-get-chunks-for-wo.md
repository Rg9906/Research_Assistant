---
title: "Remove the vestigial `text_chunks` table and `get_chunks_for_workspace` now that LlamaIndex owns chunk storage"
labels: ['refactor', 'backend', 'tech-debt']
difficulty: Medium
estimate: "3 hours"
category: "🏗 Refactor"
---

# Remove the vestigial `text_chunks` table and `get_chunks_for_workspace` now that LlamaIndex owns chunk storage

**Category:** 🏗 Refactor

## Background

CLAUDE.md §2 already documents that `WorkspaceManager`'s `text_chunks` SQLite table is "vestigial — populated with `chunks=[]` everywhere now that LlamaIndex owns chunk storage on disk" — every call site (`app/api.py::process_paper`) passes `chunks=[]`, so the table is permanently empty in current production use, yet the schema, the insert loop in `add_paper_to_workspace`, and `get_chunks_for_workspace` all still exist and are exercised by `tests/test_workspace.py`.

## Why it matters

Dead schema and dead code are exactly the kind of thing that confuses a new contributor trying to understand "where do chunks live" — they'll find two answers (SQLite table, LlamaIndex docstore) and only one is real.

## Proposed solution

Either (a) delete the `text_chunks` table, its insert loop, and `get_chunks_for_workspace` entirely (preferred, since nothing populates or reads it in production), or (b) if there's a reason to keep it for a future feature, add an explicit code comment explaining why dead code is intentionally retained. Needs a maintainer decision on which, since this touches the DB schema — flag this in the PR before assuming deletion is correct.

## Acceptance Criteria

- [ ] Either the dead `text_chunks` code path is removed (schema, insert, `get_chunks_for_workspace`) with a migration note in CHANGELOG.md, or its retention is explicitly justified in a code comment
- [ ] `tests/test_workspace.py` is updated to match whichever direction is taken
- [ ] No production code path is broken (nothing currently reads from `text_chunks`, per CLAUDE.md §2)

## Suggested files

`src/paperpilot/workspace/manager.py`, `src/app/api.py`, `tests/test_workspace.py`

## Difficulty

Medium

## Estimated time

3 hours

## Labels

refactor, backend, tech-debt

## Dependencies

None
