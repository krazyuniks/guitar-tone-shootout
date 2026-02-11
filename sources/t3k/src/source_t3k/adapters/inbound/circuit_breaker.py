"""Circuit breaker for T3K API requests.

Implements the circuit breaker pattern to prevent cascading failures
when the T3K API is unavailable or degraded.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar


class CircuitBreakerState(str, Enum):
    """Circuit breaker state enumeration.

    States:
        CLOSED: Normal operation, requests pass through
        OPEN: Breaker is open, requests are rejected immediately
        HALF_OPEN: Testing if service has recovered, allow trial requests
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker for async operations.

    Tracks consecutive failures and opens the circuit after reaching
    a threshold. After a timeout, enters half-open state to test if
    the service has recovered.

    Attributes:
        failure_threshold: Number of consecutive failures before opening
        timeout_seconds: Seconds to wait before entering half-open state
        state: Current circuit breaker state
    """

    def __init__(self, failure_threshold: int, timeout_seconds: float) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
            timeout_seconds: Seconds to wait before entering half-open state

        Raises:
            ValueError: If failure_threshold or timeout_seconds is not positive
        """
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._failure_threshold = failure_threshold
        self._timeout_seconds = timeout_seconds
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()
        self._state = CircuitBreakerState.CLOSED

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state.

        Automatically transitions from OPEN to HALF_OPEN if timeout has elapsed.

        Returns:
            Current circuit breaker state
        """
        if (
            self._state == CircuitBreakerState.OPEN
            and self._last_failure_time is not None
            and time.monotonic() - self._last_failure_time >= self._timeout_seconds
        ):
            self._state = CircuitBreakerState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Async callable to execute

        Returns:
            Result of the function call

        Raises:
            Exception: If circuit breaker is OPEN
            Exception: Re-raises any exception from the wrapped function
        """
        async with self._lock:
            current_state = self.state

            if current_state == CircuitBreakerState.OPEN:
                raise Exception("Circuit breaker is OPEN")

            try:
                result = await func()
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                # Only wrap base Exception in RuntimeError
                # Preserve more specific exception subclasses
                if type(e) is Exception:
                    raise RuntimeError(str(e)) from e
                else:
                    raise

    def _on_success(self) -> None:
        """Handle successful call - reset failure count and close breaker."""
        self._failure_count = 0
        self._state = CircuitBreakerState.CLOSED

    def _on_failure(self) -> None:
        """Handle failed call - increment failure count and open if threshold reached."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self._failure_threshold:
            self._state = CircuitBreakerState.OPEN
