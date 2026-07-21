"""
Unit tests for request pacing and the Semantic Scholar 429 backstop.

Offline: the limiter is tested against a fake clock (no real sleeping), and the
provider is tested with a stubbed httpx transport.
"""

import threading
import time

import httpx
import pytest

from paperpilot.search.providers import SemanticScholarProvider
from paperpilot.search.rate_limit import RateLimiter


class FakeClock:
    """Deterministic stand-in for time.monotonic/time.sleep."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr("paperpilot.search.rate_limit.time.monotonic", fake.monotonic)
    monkeypatch.setattr("paperpilot.search.rate_limit.time.sleep", fake.sleep)
    return fake


class TestRateLimiter:
    def test_first_call_never_waits(self, clock):
        limiter = RateLimiter(requests_per_second=1.0)
        assert limiter.acquire() == 0.0
        assert clock.sleeps == []

    def test_immediate_second_call_waits_a_full_interval(self, clock):
        limiter = RateLimiter(requests_per_second=1.0)
        limiter.acquire()
        waited = limiter.acquire()

        assert waited == pytest.approx(1.0)
        assert clock.sleeps == [pytest.approx(1.0)]

    def test_no_wait_once_the_interval_has_already_elapsed(self, clock):
        limiter = RateLimiter(requests_per_second=1.0)
        limiter.acquire()
        clock.now += 5.0  # idle longer than the interval

        assert limiter.acquire() == 0.0
        assert clock.sleeps == []

    def test_idle_period_does_not_bank_a_burst(self, clock):
        """A token bucket would let several through here; a min-interval must not."""
        limiter = RateLimiter(requests_per_second=1.0)
        limiter.acquire()
        clock.now += 10.0

        limiter.acquire()          # allowed immediately, credit is not banked
        waited = limiter.acquire() # the next one still has to wait its turn
        assert waited == pytest.approx(1.0)

    def test_rate_controls_the_interval(self, clock):
        limiter = RateLimiter(requests_per_second=2.0)
        limiter.acquire()
        assert limiter.acquire() == pytest.approx(0.5)

    def test_zero_disables_pacing(self, clock):
        limiter = RateLimiter(requests_per_second=0)
        for _ in range(5):
            assert limiter.acquire() == 0.0
        assert clock.sleeps == []

    def test_concurrent_callers_are_serialized(self):
        """Real threads, real (short) sleeps: departures must stay spaced apart.

        This is the property that matters for a per-key quota — several threads
        must never fire together. Asserting on *who* waited would be flaky,
        since a thread that happens to start late legitimately waits zero.
        """
        # 100ms, comfortably above Windows' ~15.6ms clock/sleep granularity —
        # a shorter interval makes the measurement, not the limiter, the flaky part.
        interval = 0.1
        limiter = RateLimiter(requests_per_second=1.0 / interval)
        departures: list[float] = []
        lock = threading.Lock()

        def worker():
            limiter.acquire()
            with lock:
                departures.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(departures) == 4
        departures.sort()
        gaps = [b - a for a, b in zip(departures, departures[1:])]
        # Generous tolerance: timestamps are taken after acquire() returns and
        # after lock contention, so jitter shaves a little off each gap. If the
        # limiter were broken these gaps would be ~0, not merely short.
        assert all(gap >= interval * 0.7 for gap in gaps), gaps


class TestSemanticScholarPacing:
    """The provider must pace and must survive a 429."""

    def _provider_with_transport(self, monkeypatch, responses, rps=0):
        """Build a provider whose httpx.Client returns `responses` in order."""
        calls = {"count": 0}

        def handler(request):
            index = min(calls["count"], len(responses) - 1)
            calls["count"] += 1
            status, payload = responses[index]
            return httpx.Response(status, json=payload, request=request)

        transport = httpx.MockTransport(handler)
        original_client = httpx.Client

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original_client(*args, **kwargs)

        monkeypatch.setattr("paperpilot.search.providers.httpx.Client", client_factory)
        # rps=0 disables sleeping so tests stay fast.
        return SemanticScholarProvider(api_key="k", requests_per_second=rps), calls

    def test_search_succeeds_and_parses(self, monkeypatch):
        payload = {"data": [{"title": "Attention Is All You Need", "year": 2017, "authors": [{"name": "Vaswani"}]}]}
        provider, _ = self._provider_with_transport(monkeypatch, [(200, payload)])

        papers = provider.search("transformers", limit=1)
        assert len(papers) == 1
        assert papers[0].title == "Attention Is All You Need"

    def test_429_is_retried_then_succeeds(self, monkeypatch):
        payload = {"data": [{"title": "BERT", "year": 2018, "authors": []}]}
        provider, calls = self._provider_with_transport(
            monkeypatch, [(429, {}), (200, payload)]
        )
        monkeypatch.setattr("paperpilot.search.providers.time.sleep", lambda s: None)

        papers = provider.search("bert", limit=1)
        assert calls["count"] == 2, "the 429 must be retried, not swallowed"
        assert len(papers) == 1

    def test_persistent_429_returns_empty_rather_than_raising(self, monkeypatch):
        provider, _ = self._provider_with_transport(monkeypatch, [(429, {})])
        monkeypatch.setattr("paperpilot.search.providers.time.sleep", lambda s: None)

        # One failing provider must never crash the whole search.
        assert provider.search("anything", limit=1) == []

    def test_api_key_is_sent_as_header(self, monkeypatch):
        seen = {}

        def handler(request):
            seen["key"] = request.headers.get("x-api-key")
            return httpx.Response(200, json={"data": []}, request=request)

        transport = httpx.MockTransport(handler)
        original_client = httpx.Client
        monkeypatch.setattr(
            "paperpilot.search.providers.httpx.Client",
            lambda *a, **kw: original_client(*a, **{**kw, "transport": transport}),
        )

        SemanticScholarProvider(api_key="secret-key", requests_per_second=0).search("q", limit=1)
        assert seen["key"] == "secret-key"
