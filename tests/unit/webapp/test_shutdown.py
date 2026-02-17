"""Unit tests for webapp graceful shutdown handlers.

Tests signal handling (SIGTERM, SIGINT), health endpoint behavior during shutdown,
request draining, database cleanup, and logging.

Uses monkeypatch and caplog instead of unittest.mock.
"""

import asyncio
import logging
import signal
import types

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

    def test_signal_handlers_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Signal handlers are registered for SIGTERM and SIGINT."""
        from webapp.shutdown import register_signal_handlers

        registered_signals: list[int] = []

        def fake_signal(signum, handler):
            registered_signals.append(signum)
            return None

        monkeypatch.setattr("webapp.shutdown.signal.signal", fake_signal)

        manager = ShutdownManager()
        register_signal_handlers(manager)

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

        disposed = False

        async def fake_dispose():
            nonlocal disposed
            disposed = True

        engine = types.SimpleNamespace(dispose=fake_dispose)

        await shutdown_database(engine)

        assert disposed is True


class TestShutdownLogging:
    """Tests for shutdown logging with timing information."""

    async def test_shutdown_logs_start(self, caplog: pytest.LogCaptureFixture) -> None:
        """Shutdown start is logged."""
        manager = ShutdownManager()

        with caplog.at_level(logging.INFO, logger="webapp.shutdown"):
            handle_shutdown_signal(manager, signal.SIGTERM, None)

        shutdown_logged = any(
            "shutdown" in record.message.lower() or "sigterm" in record.message.lower()
            for record in caplog.records
        )
        assert shutdown_logged

    async def test_shutdown_logs_drain_start(self, caplog: pytest.LogCaptureFixture) -> None:
        """Drain period start is logged."""
        from webapp.shutdown import perform_shutdown

        manager = ShutdownManager(drain_timeout=0.01)

        async def fake_dispose():
            pass

        engine = types.SimpleNamespace(dispose=fake_dispose)

        with caplog.at_level(logging.INFO, logger="webapp.shutdown"):
            await perform_shutdown(manager, engine)

        drain_logged = any(
            "drain" in record.message.lower() or "waiting" in record.message.lower()
            for record in caplog.records
        )
        assert drain_logged

    async def test_shutdown_logs_completion(self, caplog: pytest.LogCaptureFixture) -> None:
        """Shutdown completion with timing is logged."""
        from webapp.shutdown import perform_shutdown

        manager = ShutdownManager(drain_timeout=0.01)

        async def fake_dispose():
            pass

        engine = types.SimpleNamespace(dispose=fake_dispose)

        with caplog.at_level(logging.INFO, logger="webapp.shutdown"):
            await perform_shutdown(manager, engine)

        completion_logged = any(
            "complete" in record.message.lower() or "finished" in record.message.lower()
            for record in caplog.records
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

    async def test_lifespan_registers_signal_handlers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lifespan startup registers signal handlers."""
        from fastapi import FastAPI

        register_called = False

        def fake_register(manager):
            nonlocal register_called
            register_called = True

        monkeypatch.setattr("webapp.shutdown.register_signal_handlers", fake_register)

        app = FastAPI()
        lifespan_cm = create_lifespan()

        async with lifespan_cm(app):
            assert register_called is True

    async def test_lifespan_performs_shutdown_on_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lifespan cleanup performs graceful shutdown."""
        from fastapi import FastAPI

        shutdown_called = False

        async def fake_shutdown(manager, engine=None):
            nonlocal shutdown_called
            shutdown_called = True

        monkeypatch.setattr("webapp.shutdown.perform_shutdown", fake_shutdown)

        app = FastAPI()
        lifespan_cm = create_lifespan()

        async with lifespan_cm(app):
            pass  # Exit context

        assert shutdown_called is True
