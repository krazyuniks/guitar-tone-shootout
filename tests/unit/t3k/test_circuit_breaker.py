"""Unit tests for T3K circuit breaker.

The circuit breaker prevents cascading failures by opening after N consecutive
failures, entering a half-open state after a timeout, and closing on success.
Tests verify state transitions and failure handling.
"""

import asyncio

import pytest

from source_t3k.adapters.inbound.circuit_breaker import CircuitBreaker, CircuitBreakerState


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_starts_in_closed_state(self) -> None:
        """CircuitBreaker should start in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self) -> None:
        """CircuitBreaker should open after reaching failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        async def failing_call() -> None:
            raise Exception("API Error")

        # First 2 failures should keep it closed
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)
            assert breaker.state == CircuitBreakerState.CLOSED

        # Third failure should open it
        with pytest.raises(RuntimeError):
            await breaker.call(failing_call)
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self) -> None:
        """CircuitBreaker should reject calls immediately when OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

        async def failing_call() -> None:
            raise Exception("API Error")

        # Open the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitBreakerState.OPEN

        # Should reject without calling the function
        call_count = 0

        async def tracked_call():
            nonlocal call_count
            call_count += 1

        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await breaker.call(tracked_call)

        assert call_count == 0

    @pytest.mark.asyncio
    async def test_enters_half_open_after_timeout(self) -> None:
        """CircuitBreaker should enter HALF_OPEN state after timeout."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

        async def failing_call() -> None:
            raise Exception("API Error")

        # Open the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitBreakerState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should now be half-open (allow trial requests)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_on_success_in_half_open(self) -> None:
        """CircuitBreaker should close on successful call in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

        async def failing_call() -> None:
            raise Exception("API Error")

        async def successful_call() -> str:
            return "success"

        # Open the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # Successful call should close it
        result = await breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self) -> None:
        """CircuitBreaker should reopen on failure in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

        async def failing_call() -> None:
            raise Exception("API Error")

        # Open the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # Failure should reopen it
        with pytest.raises(RuntimeError):
            await breaker.call(failing_call)
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_resets_failure_count_on_success(self) -> None:
        """CircuitBreaker should reset failure count after successful call."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        async def failing_call() -> None:
            raise Exception("API Error")

        async def successful_call() -> str:
            return "success"

        # Record 2 failures
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitBreakerState.CLOSED

        # Successful call should reset count
        await breaker.call(successful_call)

        # Should now tolerate 2 more failures before opening
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerConfiguration:
    """Test circuit breaker configuration."""

    @pytest.mark.asyncio
    async def test_zero_failure_threshold_raises_error(self) -> None:
        """CircuitBreaker should reject zero failure threshold."""
        with pytest.raises(ValueError, match="failure_threshold must be positive"):
            CircuitBreaker(failure_threshold=0, timeout_seconds=5)

    @pytest.mark.asyncio
    async def test_negative_failure_threshold_raises_error(self) -> None:
        """CircuitBreaker should reject negative failure threshold."""
        with pytest.raises(ValueError, match="failure_threshold must be positive"):
            CircuitBreaker(failure_threshold=-1, timeout_seconds=5)

    @pytest.mark.asyncio
    async def test_zero_timeout_raises_error(self) -> None:
        """CircuitBreaker should reject zero timeout."""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            CircuitBreaker(failure_threshold=3, timeout_seconds=0)

    @pytest.mark.asyncio
    async def test_negative_timeout_raises_error(self) -> None:
        """CircuitBreaker should reject negative timeout."""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            CircuitBreaker(failure_threshold=3, timeout_seconds=-1)
