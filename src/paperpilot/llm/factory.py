"""Provider-agnostic LLM construction for both of PaperPilot's SDK layers.

Why this module exists:
    PaperPilot talks to language models through two different SDKs. The
    Planner/Tutor/Critic agents (`paperpilot.agent`) take a LangChain
    `BaseChatModel`; the RAG chat engines (`paperpilot.services.paper_chat`)
    take a LlamaIndex `LLM` installed on the global `Settings.llm`. Both have
    to answer exactly the same question first: *given the configured provider
    and whichever API keys are actually present, which backend do we talk to?*

    That question used to be answered twice — once in `app/utils.py` and once
    in `session.py` — by two hand-rolled if-chains that hardcoded model names,
    hardcoded a gemini > groq > openai precedence, and silently ignored the
    `llm_provider` setting that exists precisely to express that preference.
    The two chains were free to drift apart, which meant the Tutor and the RAG
    engine could end up on different providers without anything saying so.

    This module answers the question once. Provider *selection* lives in
    `resolve_provider_order`; per-SDK *construction* lives in two small
    builder tables that consume that ordering. Adding a fourth provider means
    adding one entry to `SUPPORTED_PROVIDERS` and one row to each table.

Selection policy:
    The provider named by `llm_provider` is tried first, then the remaining
    providers in a fixed order, and any provider without a usable API key is
    skipped entirely. So `llm_provider` is honoured when its key is present,
    but a missing or broken key degrades to a working provider instead of
    taking the whole app down — which matters because a dead LLM makes chat
    unusable while search and indexing would otherwise still work fine.

Imports are deliberately function-local: a user configured for Groq shouldn't
pay the import cost of the Google or OpenAI SDKs, and an uninstalled optional
provider package should be a skipped provider, not an ImportError at startup.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Callable

from paperpilot.config import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from langchain_core.language_models.chat_models import BaseChatModel
    from llama_index.core.llms import LLM

logger = logging.getLogger(__name__)

#: Providers this codebase knows how to build, in fallback order. The provider
#: named by `Settings.llm_provider` is promoted ahead of these at resolve time.
SUPPORTED_PROVIDERS: tuple[str, ...] = ("gemini", "groq", "openai")

#: Accepted spellings of a provider in `llm_provider` / the LLM_PROVIDER env
#: var. `.env.example` documents "google", and the SDK packages themselves use
#: several names, so normalize rather than silently falling back.
_PROVIDER_ALIASES: dict[str, str] = {
    "google": "gemini",
    "google-genai": "gemini",
    "google_genai": "gemini",
    "googlegenai": "gemini",
    "google-gemini": "gemini",
    "open-ai": "openai",
}

_ENV_KEYS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class LLMConfigurationError(RuntimeError):
    """No provider could be constructed — every candidate lacked a key or failed."""


def normalize_provider(name: str | None) -> str | None:
    """Map a user-supplied provider spelling to a canonical name, or None."""
    key = (name or "").strip().lower()
    key = _PROVIDER_ALIASES.get(key, key)
    return key if key in SUPPORTED_PROVIDERS else None


def get_api_key(provider: str, settings: Settings | None = None) -> str:
    """Return the API key for `provider`, preferring the process environment.

    The environment wins over `Settings` so that a key exported into the shell
    (or injected by a deployment) overrides whatever `.env` was baked into the
    cached settings singleton.
    """
    settings = settings or get_settings()
    env_value = os.environ.get(_ENV_KEYS[provider], "")
    settings_value = getattr(settings, f"{provider}_api_key", "") or ""
    return (env_value or settings_value).strip()


def resolve_provider_order(settings: Settings | None = None) -> list[str]:
    """Return the providers to try, best first, filtered to those with a key.

    An empty list means no provider is usable at all, which callers should
    treat as a configuration error rather than a transient failure.
    """
    settings = settings or get_settings()
    preferred = normalize_provider(settings.llm_provider)
    if settings.llm_provider and preferred is None:
        logger.warning(
            "Unknown llm_provider %r; falling back to default provider order %s",
            settings.llm_provider,
            ", ".join(SUPPORTED_PROVIDERS),
        )

    ordered = ([preferred] if preferred else []) + [
        p for p in SUPPORTED_PROVIDERS if p != preferred
    ]
    return [p for p in ordered if get_api_key(p, settings)]


def model_name_for(provider: str, settings: Settings | None = None, *, rag: bool = False) -> str:
    """Return the configured model id for `provider`.

    OpenAI keeps its two historical settings (`llm_model_name` for the agents,
    `rag_llm_model` for the RAG engine) so existing `.env` files keep working;
    the newer providers use a single model setting for both call sites.
    """
    settings = settings or get_settings()
    if provider == "openai":
        return settings.rag_llm_model if rag else settings.llm_model_name
    return getattr(settings, f"{provider}_model")


# -- LangChain builders (paperpilot.agent: Planner / Tutor / Critic) --------


def _langchain_gemini(settings: Settings) -> "BaseChatModel":  # noqa: D401
    """Build the LangChain Gemini model, forced onto the REST transport.

    `langchain-google-genai` defaults to gRPC, which does its TLS in C
    (BoringSSL) using its own bundled root store. That store ignores both
    `certifi` and the Python-level `truststore` patch, so on any machine whose
    antivirus or proxy intercepts TLS, gRPC fails every handshake with
    CERTIFICATE_VERIFY_FAILED — and retries forever rather than erroring, which
    presents as a hang, not a failure. The REST transport goes through the
    normal Python HTTP stack, so it honours the system trust store like every
    other provider here. (The gRPC-only alternative would be setting
    GRPC_DEFAULT_SSL_ROOTS_FILE_PATH to an exported CA bundle.)
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_name_for("gemini", settings),
        temperature=settings.llm_temperature,
        google_api_key=get_api_key("gemini", settings),
        transport="rest",
        # One retry, not zero and not the SDK default. Zero failed over
        # instantly on a *transient* per-minute throttle that a single
        # Retry-After sleep would have cleared; the default (several retries)
        # sits on a permanently-dead key for far too long before the fallback
        # chain gets a turn.
        max_retries=1,
    )


def _langchain_groq(settings: Settings) -> "BaseChatModel":
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model_name_for("groq", settings),
        temperature=settings.llm_temperature,
        api_key=get_api_key("groq", settings),
        max_retries=1,  # see _langchain_gemini
    )


def _langchain_openai(settings: Settings) -> "BaseChatModel":
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name_for("openai", settings),
        temperature=settings.llm_temperature,
        api_key=get_api_key("openai", settings),
        max_retries=1,  # see _langchain_gemini
    )


# -- LlamaIndex builders (services.paper_chat: the live RAG stack) ----------


def _llama_gemini(settings: Settings) -> "LLM":
    """Build a LlamaIndex Gemini LLM, preferring Google's current unified SDK.

    `llama-index-llms-gemini` wraps the retired `google.generativeai` package
    and is deprecated as of its own 0.6.2; `llama-index-llms-google-genai`
    wraps the supported `google.genai` SDK. Prefer the latter and keep the
    former as a fallback so an environment that hasn't installed the new
    package yet still gets a working Gemini rather than no LLM at all.
    """
    model = model_name_for("gemini", settings)
    api_key = get_api_key("gemini", settings)
    try:
        from llama_index.llms.google_genai import GoogleGenAI

        return GoogleGenAI(model=model, api_key=api_key, temperature=settings.llm_temperature)
    except ImportError:
        from llama_index.llms.gemini import Gemini

        logger.warning(
            "llama-index-llms-google-genai is not installed; falling back to the "
            "deprecated llama-index-llms-gemini wrapper. Install the former to "
            "stay on Google's supported SDK."
        )
        # The legacy wrapper requires the "models/" prefix on the model id.
        legacy_model = model if model.startswith("models/") else f"models/{model}"
        return Gemini(model=legacy_model, api_key=api_key, temperature=settings.llm_temperature)


def _llama_groq(settings: Settings) -> "LLM":
    from llama_index.llms.groq import Groq

    return Groq(
        model=model_name_for("groq", settings, rag=True),
        api_key=get_api_key("groq", settings),
        temperature=settings.llm_temperature,
    )


def _llama_openai(settings: Settings) -> "LLM":
    from llama_index.llms.openai import OpenAI

    return OpenAI(
        model=model_name_for("openai", settings, rag=True),
        api_key=get_api_key("openai", settings),
        temperature=settings.llm_temperature,
    )


_LANGCHAIN_BUILDERS: dict[str, Callable[[Settings], "BaseChatModel"]] = {
    "gemini": _langchain_gemini,
    "groq": _langchain_groq,
    "openai": _langchain_openai,
}

_LLAMA_BUILDERS: dict[str, Callable[[Settings], "LLM"]] = {
    "gemini": _llama_gemini,
    "groq": _llama_groq,
    "openai": _llama_openai,
}


def _build_with_provider(
    kind: str, builders: dict[str, Callable[[Settings], object]], settings: Settings | None
) -> tuple[str, object]:
    """Build the first usable provider, returning its name alongside it.

    The name matters to callers assembling a fallback chain: the winner is not
    necessarily `order[0]` (earlier providers may have failed to construct), and
    listing it again as its own fallback would just repeat a known failure.
    """
    settings = settings or get_settings()
    order = resolve_provider_order(settings)
    if not order:
        raise LLMConfigurationError(
            "No LLM API key is configured. Set one of "
            f"{', '.join(_ENV_KEYS[p] for p in SUPPORTED_PROVIDERS)} in .env or the environment."
        )

    for provider in order:
        try:
            llm = builders[provider](settings)
        except Exception as e:  # noqa: BLE001 - any SDK failure should fall through
            logger.warning(
                "Could not initialize %s LLM for provider '%s': %s", kind, provider, e
            )
            continue
        rag = kind == "LlamaIndex"
        logger.info(
            "Configured %s LLM (provider=%s, model=%s)",
            kind,
            provider,
            model_name_for(provider, settings, rag=rag),
        )
        return provider, llm

    raise LLMConfigurationError(
        f"Every configured LLM provider failed to initialize (tried: {', '.join(order)}). "
        "Check the API keys and that the corresponding SDK packages are installed."
    )


def _build(kind: str, builders: dict[str, Callable[[Settings], object]], settings: Settings | None):
    """Build the first usable provider (name discarded — see `_build_with_provider`)."""
    return _build_with_provider(kind, builders, settings)[1]


def build_chat_model(settings: Settings | None = None) -> "BaseChatModel":
    """Build the LangChain chat model for the agents, with runtime fallbacks.

    Provider *construction* succeeding says nothing about whether calls will
    work: an API key with an exhausted quota builds a perfectly valid client
    that then fails every request with a 429. That is not hypothetical — it is
    exactly what a dead OpenAI balance does, and without this the whole app is
    unusable despite other working keys being configured.

    So every remaining provider is attached via LangChain's `with_fallbacks`,
    which retries the same request on the next provider when a call raises.
    With a single usable provider the plain model is returned unchanged.

    Raises:
        LLMConfigurationError: if no provider could be constructed at all.
    """
    settings = settings or get_settings()
    primary_name, primary = _build_with_provider("LangChain", _LANGCHAIN_BUILDERS, settings)

    fallbacks = []
    used = [primary_name]
    for provider in resolve_provider_order(settings):
        if provider == primary_name:
            continue
        try:
            fallbacks.append(_LANGCHAIN_BUILDERS[provider](settings))
            used.append(provider)
        except Exception as e:  # noqa: BLE001
            logger.warning("Fallback provider '%s' unavailable: %s", provider, e)

    if not fallbacks:
        return primary  # type: ignore[return-value]

    logger.info("LLM fallback chain active: %s", " -> ".join(used))
    return primary.with_fallbacks(fallbacks)  # type: ignore[union-attr,return-value]


def build_llama_llm(settings: Settings | None = None) -> "LLM":
    """Build the LlamaIndex LLM backing the live RAG chat engines.

    Raises:
        LLMConfigurationError: if no provider could be constructed.
    """
    return _build("LlamaIndex", _LLAMA_BUILDERS, settings)  # type: ignore[return-value]
