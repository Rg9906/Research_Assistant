"""Network trust configuration.

Why this exists:
    Python's TLS verification uses `certifi`'s CA bundle, which contains only
    public root CAs. On machines behind a TLS-intercepting middlebox — most
    consumer antivirus suites (Kaspersky, Avast, ESET, Bitdefender) and nearly
    every corporate proxy — HTTPS connections are re-signed by a locally
    installed root CA. That CA is trusted by Windows, but `certifi` has never
    heard of it, so every outbound HTTPS call fails with:

        [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate

    This affects every remote call PaperPilot makes: arXiv, Semantic Scholar,
    Hugging Face model downloads, and all three LLM providers.

    `truststore` makes Python verify against the *operating system's* trust
    store instead of the bundled one, so the locally installed CA is honoured.
    Verification stays fully enabled — this is not `verify=False`, and it must
    never be replaced by that. Disabling verification would make the app
    silently accept any certificate, which for an app that carries API keys in
    request headers means handing those keys to whoever is intercepting.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger(__name__)

_injected = False


def enable_system_trust_store() -> bool:
    """Verify TLS against the OS trust store. Returns True if enabled.

    Safe to call more than once; the underlying patch is applied at most once.
    A missing `truststore` package is not an error — on a machine without TLS
    interception, certifi's bundle works fine and nothing needs to change.
    """
    global _injected
    if _injected:
        return True

    try:
        import truststore
    except ImportError:
        logger.debug("truststore not installed; using certifi's CA bundle.")
        return False

    try:
        truststore.inject_into_ssl()
    except Exception as e:
        # Never let trust configuration prevent startup — the app may well be
        # on a network where the default bundle is sufficient.
        logger.warning("Could not enable the system trust store: %s", e)
        return False

    _injected = True
    logger.info("TLS verification is using the system trust store.")
    return True


def _hf_cache_has(model_names: Iterable[str]) -> bool:
    """True only if every named model is already in the local Hugging Face cache.

    Matches on the repo's last path segment so a bare model name
    ("all-MiniLM-L6-v2") matches its full repo id
    ("sentence-transformers/all-MiniLM-L6-v2") that the loader expands it to.
    """
    wanted = {n.strip().split("/")[-1] for n in model_names if n and n.strip()}
    if not wanted:
        return False
    try:
        from huggingface_hub import scan_cache_dir

        cached = {repo.repo_id.split("/")[-1] for repo in scan_cache_dir().repos}
    except Exception as e:
        # No huggingface_hub, an unreadable cache, or a format change: treat as
        # "not confidently cached" and stay online rather than risk blocking a
        # needed download.
        logger.debug("Could not scan the Hugging Face cache: %s", e)
        return False
    return wanted <= cached


def enable_hf_offline_if_cached(model_names: Iterable[str]) -> bool:
    """Skip Hugging Face's update check when every model is already downloaded.

    Why:
        On each start, the embedding loaders HEAD huggingface.co to check for a
        newer model revision. When that host is unreachable — flaky DNS, offline
        laptop, restrictive network — the check retries several times per model
        before falling back to the on-disk copy, adding minutes to startup for
        no benefit. Setting HF_HUB_OFFLINE tells the libraries to use the cache
        directly and skip the network entirely.

    Safety:
        Only enabled when the models are confirmed present in the cache, so a
        first run (nothing cached yet) still goes online to download them.
        An explicit HF_HUB_OFFLINE in the environment is always respected and
        never overridden. Must run before the embedding libraries load a model.

    Returns True if offline mode is now in effect (whether we set it or the user did).
    """
    if os.environ.get("HF_HUB_OFFLINE") in ("1", "true", "True"):
        return True

    if _hf_cache_has(model_names):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"  # sentence-transformers reads this one
        logger.info("All embedding models are cached; enabling Hugging Face offline mode.")
        return True

    logger.info("Embedding models not fully cached; staying online so they can download.")
    return False
