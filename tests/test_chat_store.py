"""
Unit tests for WorkspaceChatStore's DB-backed persistence.

Fully offline: uses a real WorkspaceManager against a tmp_path SQLite file (no
mocking needed since sqlite3 is already local/offline), so these prove actual
persistence rather than just the in-memory cache layer.
"""

from llama_index.core.llms import ChatMessage

from app.utils import WorkspaceChatStore
from paperpilot.config import get_settings
from paperpilot.workspace.manager import WorkspaceManager


def make_db(tmp_path):
    return WorkspaceManager(db_path=tmp_path / "workspace.db")


class TestWorkspaceChatStore:
    def test_get_on_empty_workspace_returns_empty_list(self, tmp_path):
        db = make_db(tmp_path)
        ws_id = db.create_workspace("Empty")
        store = WorkspaceChatStore(db=db)

        assert store.get(ws_id) == []

    def test_set_then_get_round_trips(self, tmp_path):
        db = make_db(tmp_path)
        ws_id = db.create_workspace("WS")
        store = WorkspaceChatStore(db=db)

        history = [ChatMessage(role="user", content="hi"), ChatMessage(role="assistant", content="hello")]
        store.set(ws_id, history)

        result = store.get(ws_id)
        assert [(m.role.value, m.content) for m in result] == [("user", "hi"), ("assistant", "hello")]

    def test_persists_across_a_fresh_store_instance(self, tmp_path):
        """Proves the DB write-through, not just the in-memory cache."""
        db = make_db(tmp_path)
        ws_id = db.create_workspace("WS")
        store = WorkspaceChatStore(db=db)
        store.set(ws_id, [ChatMessage(role="user", content="persisted?")])

        fresh_store = WorkspaceChatStore(db=db)
        result = fresh_store.get(ws_id)
        assert len(result) == 1
        assert result[0].content == "persisted?"

    def test_trims_to_memory_max_messages(self, tmp_path, monkeypatch):
        db = make_db(tmp_path)
        ws_id = db.create_workspace("WS")
        store = WorkspaceChatStore(db=db)

        get_settings.cache_clear()
        monkeypatch.setenv("MEMORY_MAX_MESSAGES", "4")
        get_settings.cache_clear()
        try:
            long_history = [ChatMessage(role="user", content=str(i)) for i in range(10)]
            store.set(ws_id, long_history)
            result = store.get(ws_id)
            assert len(result) == 4
            assert [m.content for m in result] == ["6", "7", "8", "9"]
        finally:
            get_settings.cache_clear()

    def test_clear_empties_cache_and_db(self, tmp_path):
        db = make_db(tmp_path)
        ws_id = db.create_workspace("WS")
        store = WorkspaceChatStore(db=db)
        store.set(ws_id, [ChatMessage(role="user", content="hi")])

        store.clear(ws_id)

        assert store.get(ws_id) == []
        assert db.get_chat_messages(ws_id) == []

    def test_workspace_deletion_cascades_chat_history(self, tmp_path):
        db = make_db(tmp_path)
        ws_id = db.create_workspace("WS")
        store = WorkspaceChatStore(db=db)
        store.set(ws_id, [ChatMessage(role="user", content="hi")])

        db.delete_workspace(ws_id)

        assert db.get_chat_messages(ws_id) == []
