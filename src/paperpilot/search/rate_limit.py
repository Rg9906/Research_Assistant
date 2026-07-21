"""Client-side request pacing for rate-limited academic APIs.

Why pace requests at all, rather than just handling 429s:
    Semantic Scholar issues per-key quotas (1 request/second on the standard
    grant). Discovering the limit by being rejected is wasteful — a 429 costs a
    full round-trip, returns no data, and repeated violations risk the key
    itself. Spacing requests locally means the limit is essentially never hit.

Why a minimum-interval limiter rather than a token bucket:
    A token bucket permits bursts by design: after an idle period it would let
    several requests through back-to-back, which is exactly what a strict
    "1 per second" quota rejects. Enforcing a floor on the gap between
    consecutive requests is the behaviour the quota actually describes.

Why the lock is held across the sleep:
    FastAPI runs synchronous route handlers in a thread pool, so two concurrent
    searches really can call this from different threads. If each thread merely
    read the timestamp, slept, and then updated it, both would compute the same
    departure slot and fire together — the burst the limiter exists to prevent.
    Holding the lock while sleeping serializes callers into a queue, which is
    the correct shape for a global per-key quota.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Enforces a minimum interval between calls to `acquire()`, across threads."""

    def __init__(self, requests_per_second: float) -> None:
        """Initialize the limiter.

        Args:
            requests_per_second: Sustained request rate to allow. Values <= 0
                disable pacing entirely (useful for tests and for providers
                with no published quota).
        """
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._lock = threading.Lock()
        # -inf rather than 0 so the very first call never sleeps, regardless of
        # how the monotonic clock's origin relates to wall time.
        self._last_call = float("-inf")

    def acquire(self) -> float:
        """Block until the next request is allowed. Returns seconds waited."""
        if self.min_interval <= 0:
            return 0.0

        with self._lock:
            # monotonic, not time(): a clock adjustment (NTP sync, DST) must not
            # make the limiter either stall for hours or release a burst.
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_call)
            if wait > 0:
                logger.debug("Rate limiter sleeping %.3fs", wait)
                time.sleep(wait)
                self._last_call = time.monotonic()
                return wait
            self._last_call = now
            return 0.0
