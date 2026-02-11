"""Rate limiter for T3K API requests.

Implements a token bucket rate limiter to enforce per-endpoint
request limits and avoid hitting T3K API rate limits.
"""

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter for async requests.

    Enforces a maximum requests-per-second limit by delaying
    requests that exceed the configured rate.

    Attributes:
        requests_per_second: Maximum number of requests per second
    """

    def __init__(self, requests_per_second: float) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum number of requests per second

        Raises:
            ValueError: If requests_per_second is not positive
        """
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self._requests_per_second = requests_per_second
        self._max_tokens = requests_per_second
        self._tokens = requests_per_second
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Blocks until the request can proceed without exceeding
        the rate limit.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_update

                # Refill tokens based on time elapsed
                self._tokens = min(
                    self._max_tokens, self._tokens + elapsed * self._requests_per_second
                )
                self._last_update = now

                # If we have at least 1 token, consume it and proceed
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    break

                # Calculate how long to wait for the next token
                tokens_needed = 1.0 - self._tokens
                wait_time = tokens_needed / self._requests_per_second
                await asyncio.sleep(wait_time)
