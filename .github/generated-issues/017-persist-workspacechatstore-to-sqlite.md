# Persist `WorkspaceChatStore` to SQLite instead of an in-memory dict

## Background

`WorkspaceChatStore` (`src/app/utils.py`) holds every workspace's chat
history in a process-local `dict`, explicitly documented as a known
limitation:

```python
class WorkspaceChatStore:
    """Process-local store of per-workspace chat memory.
    ...
    This is an in-memory dict ... history does not survive a server
    restart. Persisting it to the workspace DB is future work if
    cross-restart memory is needed.
    """
```

ROADMAP.md lists "Long-term memory" (persisting conversation/workspace
memory across restarts) as planned/future work. This issue operationalizes
that specific line.

## Why it matters

Every server restart (a deploy, a crash, a routine `--reload` during
development) silently wipes every in-progress conversation. For a tool
whose whole pitch is "chat with your papers," losing conversation context
on restart is a real, user-visible regression from what most chat products
guarantee, and it's explicitly flagged as a gap the maintainers already
know about.

## Proposed solution

Add a `workspace_chat_history` table to the existing `workspace.db` SQLite
database (via `WorkspaceManager`, keeping the "one database" convention
already established), storing the serialized `ChatMessage` list per
`workspace_id`. `WorkspaceChatStore.get`/`set` become thin wrappers around
reads/writes to that table instead of dict access, keeping the same public
interface so `app/api.py` doesn't need to change at all.

This should land after (or alongside) #004 (WAL mode), since chat history
writes happen on every single chat turn — the most frequent write path in
the app — and benefit most from safe concurrent access.

## Acceptance criteria

- [ ] Chat history for a workspace survives a server restart.
- [ ] `WorkspaceChatStore.get`/`set` keep their existing signatures — no
      caller changes required.
- [ ] A test restarts (re-instantiates) the store against the same
      on-disk DB and confirms history is recovered.
- [ ] `delete_workspace` continues to clear the associated chat history
      (cascading delete, matching the existing `ON DELETE CASCADE`
      convention for `workspace_papers`).

## Suggested files

- `src/app/utils.py`
- `src/paperpilot/workspace/manager.py`
- `tests/test_workspace.py`

## Difficulty

Medium

## Estimated time

1 day

## Labels

`enhancement`, `backend`, `feature`

## Dependencies

Recommended after #004 (WAL mode) for safe concurrent writes on the
highest-frequency write path in the app.
