"""
Unit tests for provider resolution in paperpilot.llm.factory.

These tests never construct a real SDK client: provider *selection* is the
logic worth testing, and the per-provider builders are thin constructor calls
that would require network access and live API keys. The builder tables are
dependency-injected into `_build` for that reason, so fallback behaviour can be
exercised with plain callables.

Every test builds an explicit Settings object and clears the three API-key
environment variables, so results never depend on whatever .env the developer
running the suite happens to have.
"""

import pytest

from paperpilot.config import Settings
from paperpilot.llm.factory import (
    LLMConfigurationError,
    _build,
    get_api_key,
    model_name_for,
    normalize_provider,
    resolve_provider_order,
)


@pytest.fixture(autouse=True)
def _clear_key_env(monkeypatch):
    """Isolate tests from a developer's real exported API keys."""
    for var in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def make_settings(**overrides) -> Settings:
    """Settings with all keys blank by default, ignoring any ambient .env."""
    base = {
        "llm_provider": "openai",
        "openai_api_key": "",
        "gemini_api_key": "",
        "groq_api_key": "",
    }
    base.update(overrides)
    return Settings(**base)


class TestNormalizeProvider:
    """Provider names arrive from user-edited .env files, so spellings vary."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("openai", "openai"),
            ("OpenAI", "openai"),
            ("  groq  ", "groq"),
            ("gemini", "gemini"),
            ("google", "gemini"),
            ("google-genai", "gemini"),
            ("anthropic", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalization(self, raw, expected):
        assert normalize_provider(raw) == expected


class TestResolveProviderOrder:
    """The configured provider leads; providers without a key drop out."""

    def test_configured_provider_is_tried_first(self):
        settings = make_settings(
            llm_provider="groq", groq_api_key="g", gemini_api_key="x", openai_api_key="o"
        )
        assert resolve_provider_order(settings)[0] == "groq"

    def test_providers_without_keys_are_excluded(self):
        settings = make_settings(llm_provider="openai", gemini_api_key="x")
        assert resolve_provider_order(settings) == ["gemini"]

    def test_no_keys_yields_empty_order(self):
        assert resolve_provider_order(make_settings()) == []

    def test_unknown_provider_falls_back_to_default_order(self):
        settings = make_settings(
            llm_provider="anthropic", gemini_api_key="x", openai_api_key="o"
        )
        # Unknown preference is ignored rather than fatal; default order stands.
        assert resolve_provider_order(settings) == ["gemini", "openai"]

    def test_environment_key_overrides_blank_settings(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "from-env")
        settings = make_settings(llm_provider="groq")
        assert get_api_key("groq", settings) == "from-env"
        assert resolve_provider_order(settings) == ["groq"]


class TestModelNameFor:
    """OpenAI keeps its two historical model settings; others use one."""

    def test_openai_splits_agent_and_rag_models(self):
        settings = make_settings(llm_model_name="gpt-4o", rag_llm_model="gpt-4o-mini")
        assert model_name_for("openai", settings) == "gpt-4o"
        assert model_name_for("openai", settings, rag=True) == "gpt-4o-mini"

    def test_other_providers_share_one_model_setting(self):
        settings = make_settings(gemini_model="gemini-2.5-flash")
        assert model_name_for("gemini", settings) == "gemini-2.5-flash"
        assert model_name_for("gemini", settings, rag=True) == "gemini-2.5-flash"


class TestRuntimeFallbackChain:
    """Construction succeeding doesn't mean calls will (e.g. an exhausted quota)."""

    def test_multiple_providers_produce_a_fallback_chain(self, monkeypatch):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from paperpilot.llm import factory

        settings = make_settings(llm_provider="openai", openai_api_key="o", groq_api_key="g")
        monkeypatch.setattr(
            factory,
            "_LANGCHAIN_BUILDERS",
            {p: (lambda _s: FakeListChatModel(responses=["hi"])) for p in ("gemini", "groq", "openai")},
        )

        model = factory.build_chat_model(settings)
        # A RunnableWithFallbacks, not a bare chat model.
        assert hasattr(model, "fallbacks")
        assert len(model.fallbacks) == 1  # groq only; openai is the primary

    def test_single_provider_returns_a_plain_model(self, monkeypatch):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from paperpilot.llm import factory

        settings = make_settings(llm_provider="groq", groq_api_key="g")
        monkeypatch.setattr(
            factory,
            "_LANGCHAIN_BUILDERS",
            {p: (lambda _s: FakeListChatModel(responses=["hi"])) for p in ("gemini", "groq", "openai")},
        )

        model = factory.build_chat_model(settings)
        assert not hasattr(model, "fallbacks")

    def test_a_failing_call_is_retried_on_the_next_provider(self, monkeypatch):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from paperpilot.llm import factory

        class DeadQuotaModel(FakeListChatModel):
            def _call(self, *args, **kwargs):
                raise RuntimeError("429 insufficient_quota")

        settings = make_settings(llm_provider="openai", openai_api_key="o", groq_api_key="g")
        builders = {
            "openai": lambda _s: DeadQuotaModel(responses=["never"]),
            "groq": lambda _s: FakeListChatModel(responses=["from the fallback"]),
            "gemini": lambda _s: FakeListChatModel(responses=["unused"]),
        }
        monkeypatch.setattr(factory, "_LANGCHAIN_BUILDERS", builders)

        model = factory.build_chat_model(settings)
        assert model.invoke("hello").content == "from the fallback"


class TestBuildFallback:
    """A provider whose SDK blows up must not take the whole app down."""

    def test_falls_through_to_next_provider_on_failure(self):
        settings = make_settings(
            llm_provider="gemini", gemini_api_key="x", openai_api_key="o"
        )

        def boom(_settings):
            raise RuntimeError("SDK exploded")

        builders = {"gemini": boom, "groq": boom, "openai": lambda _s: "openai-llm"}
        assert _build("Test", builders, settings) == "openai-llm"

    def test_raises_when_no_key_is_configured(self):
        with pytest.raises(LLMConfigurationError, match="No LLM API key"):
            _build("Test", {}, make_settings())

    def test_raises_when_every_candidate_fails(self):
        settings = make_settings(llm_provider="groq", groq_api_key="g")

        def boom(_settings):
            raise RuntimeError("SDK exploded")

        with pytest.raises(LLMConfigurationError, match="failed to initialize"):
            _build("Test", {"groq": boom}, settings)
