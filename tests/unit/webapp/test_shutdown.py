"""Unit tests for webapp graceful shutdown handlers.

Tests signal handling (SIGTERM, SIGINT), health endpoint behavior during shutdown,
request draining, database cleanup, and logging.
"""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webapp.shutdown import (
    ShutdownManager,
    create_lifespan,
    handle_shutdown_signal,
)


class TestShutdownManager:
    """Tests for ShutdownManager state and lifecycle."""

    def test_initial_state(self) -> None:
        """ShutdownManager starts in ready state."""
        manager = ShutdownManager(drain_timeout=30.0)

        assert manager.is_shutting_down is False
        assert manager.drain_timeout == 30.0

    def test_start_shutdown(self) -> None:
        """start_shutdown marks manager as shutting down."""
        manager = ShutdownManager(drain_timeout=30.0)

        assert manager.is_shutting_down is False

        manager.start_shutdown()

        assert manager.is_shutting_down is True

    def test_default_drain_timeout(self) -> None:
        """ShutdownManager defaults to 30s drain timeout."""
        manager = ShutdownManager()

        assert manager.drain_timeout == 30.0

    def test_custom_drain_timeout(self) -> None:
        """ShutdownManager accepts custom drain timeout."""
        manager = ShutdownManager(drain_timeout=60.0)

        assert manager.drain_timeout == 60.0

    def test_is_ready_when_not_shutting_down(self) -> None:
        """is_ready returns True before shutdown starts."""
        manager = ShutdownManager()

        assert manager.is_ready() is True

    def test_is_ready_when_shutting_down(self) -> None:
        """is_ready returns False during shutdown."""
        manager = ShutdownManager()

        manager.start_shutdown()

        assert manager.is_ready() is False


class TestSignalHandling:
    """Tests for SIGTERM and SIGINT signal handlers."""

    def test_handle_shutdown_signal_for_sigterm(self) -> None:
        """handle_shutdown_signal handles SIGTERM."""
        manager = ShutdownManager()

        assert manager.is_shutting_down is False

        handle_shutdown_signal(manager, signal.SIGTERM, None)

        assert manager.is_shutting_down is True

    def test_handle_shutdown_signal_for_sigint(self) -> None:
        """handle_shutdown_signal handles SIGINT (Ctrl+C)."""
        manager = ShutdownManager()

        assert manager.is_shutting_down is False

        handle_shutdown_signal(manager, signal.SIGINT, None)

        assert manager.is_shutting_down is True

    @patch("webapp.shutdown.signal.signal")
    def test_signal_handlers_registered(self, mock_signal: MagicMock) -> None:
        """Signal handlers are registered for SIGTERM and SIGINT."""
        from webapp.shutdown import register_signal_handlers

        manager = ShutdownManager()

        register_signal_handlers(manager)

        # Should register handlers for both SIGTERM and SIGINT
        assert mock_signal.call_count >= 2

        # Extract all signal numbers that were registered
        registered_signals = [call[0][0] for call in mock_signal.call_args_list]

        assert signal.SIGTERM in registered_signals
        assert signal.SIGINT in registered_signals


class TestHealthEndpointDuringShutdown:
    """Tests for health endpoint 503 response during shutdown."""

    async def test_health_returns_ready_before_shutdown(self) -> None:
        """Health endpoint returns ready status before shutdown."""
        from webapp.shutdown import get_health_status

        manager = ShutdownManager()

        status = await get_health_status(manager)

        assert status["status"] == "ready"
        assert status["shutting_down"] is False

    async def test_health_returns_unavailable_during_shutdown(self) -> None:
        """Health endpoint returns 503 unavailable during shutdown."""
        from webapp.shutdown import get_health_status

        manager = ShutdownManager()
        manager.start_shutdown()

        status = await get_health_status(manager)

        assert status["status"] == "unavailable"
        assert status["shutting_down"] is True


class TestRequestDraining:
    """Tests for request draining during shutdown period."""

    async def test_in_flight_requests_tracked(self) -> None:
        """ShutdownManager tracks in-flight requests."""
        manager = ShutdownManager()

        assert manager.in_flight_requests == 0

        manager.increment_in_flight()
        assert manager.in_flight_requests == 1

        manager.increment_in_flight()
        assert manager.in_flight_requests == 2

    async def test_in_flight_requests_decremented(self) -> None:
        """ShutdownManager decrements in-flight requests on completion."""
        manager = ShutdownManager()

        manager.increment_in_flight()
        manager.increment_in_flight()
        assert manager.in_flight_requests == 2

        manager.decrement_in_flight()
        assert manager.in_flight_requests == 1

        manager.decrement_in_flight()
        assert manager.in_flight_requests == 0

    async def test_wait_for_in_flight_requests_with_no_requests(self) -> None:
        """wait_for_in_flight completes immediately if no requests in flight."""
        manager = ShutdownManager()

        # Should complete immediately
        await asyncio.wait_for(manager.wait_for_in_flight(), timeout=0.1)

    async def test_wait_for_in_flight_requests_blocks_until_complete(self) -> None:
        """wait_for_in_flight blocks until all requests complete."""
        manager = ShutdownManager()

        manager.increment_in_flight()

        # Start waiting in background
        wait_task = asyncio.create_task(manager.wait_for_in_flight())

        # Should not complete immediately
        await asyncio.sleep(0.01)
        assert not wait_task.done()

        # Complete the request
        manager.decrement_in_flight()

        # Should complete now
        await asyncio.wait_for(wait_task, timeout=0.1)
        assert wait_task.done()

    async def test_wait_for_in_flight_respects_timeout(self) -> None:
        """wait_for_in_flight times out after drain_timeout seconds."""
        manager = ShutdownManager(drain_timeout=0.05)

        # Simulate a stuck request
        manager.increment_in_flight()

        # Should time out after drain_timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                manager.wait_for_in_flight(),
                timeout=0.1,  # Slightly longer than drain_timeout
            )


class TestDatabaseShutdown:
    """Tests for database connection pool cleanup."""

    async def test_shutdown_closes_db_engine(self) -> None:
        """Shutdown manager closes database engine."""
        from webapp.shutdown import shutdown_database

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        await shutdown_database(mock_engine)

        mock_engine.dispose.assert_called_once()


class TestShutdownLogging:
    """Tests for shutdown logging with timing information."""

    @patch("webapp.shutdown.logger")
    async def test_shutdown_logs_start(self, mock_logger: MagicMock) -> None:
        """Shutdown start is logged."""
        manager = ShutdownManager()

        handle_shutdown_signal(manager, signal.SIGTERM, None)

        # Should log shutdown initiation
        mock_logger.info.assert_called()

        # Check that the log message mentions shutdown
        call_args = mock_logger.info.call_args_list
        shutdown_logged = any(
            "shutdown" in str(call).lower() or "sigterm" in str(call).lower() for call in call_args
        )
        assert shutdown_logged

    @patch("webapp.shutdown.logger")
    async def test_shutdown_logs_drain_start(self, mock_logger: MagicMock) -> None:
        """Drain period start is logged."""
        from webapp.shutdown import perform_shutdown

        manager = ShutdownManager(drain_timeout=0.01)
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        await perform_shutdown(manager, mock_engine)

        # Should log drain period
        call_args = [str(call) for call in mock_logger.info.call_args_list]
        drain_logged = any("drain" in msg.lower() or "waiting" in msg.lower() for msg in call_args)
        assert drain_logged

    @patch("webapp.shutdown.logger")
    async def test_shutdown_logs_completion(self, mock_logger: MagicMock) -> None:
        """Shutdown completion with timing is logged."""
        from webapp.shutdown import perform_shutdown

        manager = ShutdownManager(drain_timeout=0.01)
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        await perform_shutdown(manager, mock_engine)

        # Should log shutdown completion
        call_args = [str(call) for call in mock_logger.info.call_args_list]
        completion_logged = any(
            "complete" in msg.lower() or "finished" in msg.lower() for msg in call_args
        )
        assert completion_logged


class TestLifespanIntegration:
    """Tests for FastAPI lifespan context manager integration."""

    async def test_lifespan_creates_shutdown_manager(self) -> None:
        """Lifespan context manager creates ShutdownManager."""
        from fastapi import FastAPI

        app = FastAPI()
        lifespan_cm = create_lifespan()

        # Context manager should create manager and yield app
        async with lifespan_cm(app) as state:
            assert "shutdown_manager" in state
            assert isinstance(state["shutdown_manager"], ShutdownManager)

    async def test_lifespan_registers_signal_handlers(self) -> None:
        """Lifespan startup registers signal handlers."""
        from fastapi import FastAPI

        app = FastAPI()
        lifespan_cm = create_lifespan()

        with patch("webapp.shutdown.register_signal_handlers") as mock_register:
            async with lifespan_cm(app):
                # Signal handlers should be registered
                mock_register.assert_called_once()

    async def test_lifespan_performs_shutdown_on_exit(self) -> None:
        """Lifespan cleanup performs graceful shutdown."""
        from fastapi import FastAPI

        app = FastAPI()
        lifespan_cm = create_lifespan()

        with patch("webapp.shutdown.perform_shutdown", new_callable=AsyncMock) as mock_shutdown:
            async with lifespan_cm(app):
                pass  # Exit context

            # Shutdown should be performed on exit
            mock_shutdown.assert_called_once()
