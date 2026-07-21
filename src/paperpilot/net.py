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
