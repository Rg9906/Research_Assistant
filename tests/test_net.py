"""
Unit tests for network/trust helpers (paperpilot.net).

The Hugging Face cache scan is stubbed, so these never touch the real cache or
the network.
"""

import types

import pytest

from paperpilot import net


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)


def _fake_scan(*repo_ids):
    """Build a stand-in for huggingface_hub.scan_cache_dir()."""
    repos = [types.SimpleNamespace(repo_id=rid) for rid in repo_ids]

    def scan_cache_dir():
        return types.SimpleNamespace(repos=repos)

    return scan_cache_dir


def _install_fake_hub(monkeypatch, scan):
    fake_hub = types.SimpleNamespace(scan_cache_dir=scan)
    monkeypatch.setitem(__import__("sys").modules, "huggingface_hub", fake_hub)


class TestHfCacheHas:
    def test_bare_name_matches_full_repo_id(self, monkeypatch):
        _install_fake_hub(monkeypatch, _fake_scan("sentence-transformers/all-MiniLM-L6-v2"))
        assert net._hf_cache_has(["all-MiniLM-L6-v2"]) is True

    def test_all_models_must_be_present(self, monkeypatch):
        _install_fake_hub(monkeypatch, _fake_scan("BAAI/bge-small-en-v1.5"))
        # bge is cached, MiniLM is not -> not fully cached
        assert net._hf_cache_has(["BAAI/bge-small-en-v1.5", "all-MiniLM-L6-v2"]) is False

    def test_empty_input_is_false(self, monkeypatch):
        _install_fake_hub(monkeypatch, _fake_scan("BAAI/bge-small-en-v1.5"))
        assert net._hf_cache_has([]) is False

    def test_scan_failure_is_treated_as_not_cached(self, monkeypatch):
        def boom():
            raise OSError("cache unreadable")

        _install_fake_hub(monkeypatch, boom)
        assert net._hf_cache_has(["anything"]) is False


class TestEnableHfOfflineIfCached:
    def test_sets_offline_when_all_cached(self, monkeypatch):
        _install_fake_hub(
            monkeypatch,
            _fake_scan("BAAI/bge-small-en-v1.5", "sentence-transformers/all-MiniLM-L6-v2"),
        )
        assert net.enable_hf_offline_if_cached(["BAAI/bge-small-en-v1.5", "all-MiniLM-L6-v2"])
        import os
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"

    def test_stays_online_when_not_cached(self, monkeypatch):
        import os

        _install_fake_hub(monkeypatch, _fake_scan("BAAI/bge-small-en-v1.5"))
        assert net.enable_hf_offline_if_cached(["all-MiniLM-L6-v2"]) is False
        # Crucially: a first run must not be forced offline, or the download it
        # needs would be blocked.
        assert "HF_HUB_OFFLINE" not in os.environ

    def test_respects_a_user_set_offline_flag(self, monkeypatch):
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        # Even with nothing cached, an explicit user setting wins and no scan is needed.
        assert net.enable_hf_offline_if_cached(["not-cached"]) is True
