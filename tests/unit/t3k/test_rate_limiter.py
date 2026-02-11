"""Unit tests for T3K rate limiter.

The rate limiter enforces per-endpoint request limits to avoid hitting
T3K API rate limits. Tests verify that requests are throttled according
to configured limits.
"""

import asyncio
import time

import pytest

from source_t3k.adapters.inbound.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self) -> None:
        """RateLimiter should allow requests within the rate limit."""
        limiter = RateLimiter(requests_per_second=10)

        # Should allow 5 requests immediately (well under limit)
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_throttles_requests_exceeding_limit(self) -> None:
        """RateLimiter should throttle requests exceeding the rate limit."""
        limiter = RateLimiter(requests_per_second=2)

        # First 2 requests should be immediate
        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        elapsed_immediate = time.monotonic() - start

        # Should be nearly instant (< 0.1s)
        assert elapsed_immediate < 0.1

        # Third request should be delayed
        start = time.monotonic()
        await limiter.acquire()
        elapsed_delayed = time.monotonic() - start

        # Should wait approximately 0.5s (to meet 2 req/s limit)
        assert elapsed_delayed >= 0.4  # Allow some margin

    @pytest.mark.asyncio
    async def test_resets_after_time_window(self) -> None:
        """RateLimiter should reset after the time window passes."""
        limiter = RateLimiter(requests_per_second=5)

        # Use up the limit
        for _ in range(5):
            await limiter.acquire()

        # Wait for window to reset (1 second / 5 req/s = 0.2s per request)
        await asyncio.sleep(1.1)

        # Should allow immediate request again
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_different_endpoints_have_independent_limits(self) -> None:
        """RateLimiter instances should maintain independent limits."""
        limiter_a = RateLimiter(requests_per_second=2)
        limiter_b = RateLimiter(requests_per_second=2)

        # Use up limit on limiter_a
        await limiter_a.acquire()
        await limiter_a.acquire()

        # limiter_b should still allow immediate requests
        start = time.monotonic()
        await limiter_b.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_serialized(self) -> None:
        """RateLimiter should serialize concurrent requests."""
        limiter = RateLimiter(requests_per_second=2)

        # Fire off 4 concurrent requests
        start = time.monotonic()
        await asyncio.gather(
            limiter.acquire(),
            limiter.acquire(),
            limiter.acquire(),
            limiter.acquire(),
        )
        elapsed = time.monotonic() - start

        # Should take approximately 1.5s to process 4 requests at 2 req/s
        # (0s for first 2, ~0.5s for 3rd, ~1.0s for 4th)
        assert elapsed >= 1.0
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_zero_requests_per_second_raises_error(self) -> None:
        """RateLimiter should reject zero requests per second."""
        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            RateLimiter(requests_per_second=0)

    @pytest.mark.asyncio
    async def test_negative_requests_per_second_raises_error(self) -> None:
        """RateLimiter should reject negative requests per second."""
        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            RateLimiter(requests_per_second=-1)
