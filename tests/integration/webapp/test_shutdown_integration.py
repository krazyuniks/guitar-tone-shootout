"""Integration tests for webapp graceful shutdown with FastAPI.

Tests shutdown behavior in the context of a running FastAPI application,
including request handling during drain, health endpoint responses, and
lifespan event integration.
"""

import asyncio
import signal
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import InvalidRequestError, OperationalError

from webapp.shutdown import ShutdownManager, create_lifespan


@pytest.mark.integration
@pytest.mark.asyncio
class TestShutdownWithFastAPI:
    """Integration tests with FastAPI application."""

    @pytest.fixture
    async def app_with_shutdown(self) -> AsyncGenerator[tuple[FastAPI, ShutdownManager], None]:
        """Create FastAPI app with shutdown manager."""
        app = FastAPI(lifespan=create_lifespan())

        # Access the shutdown manager from app state after startup
        # In the real implementation, this will be set during lifespan startup
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test"):
            # Lifespan events run when AsyncClient starts
            manager = app.state.shutdown_manager
            yield app, manager

    async def test_health_endpoint_returns_503_during_shutdown(
        self, app_with_shutdown: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """Health endpoint returns 503 when shutdown is in progress."""
        app, manager = app_with_shutdown

        # Start shutdown
        manager.start_shutdown()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unavailable"
            assert data["shutting_down"] is True

    async def test_health_endpoint_returns_200_before_shutdown(
        self, app_with_shutdown: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """Health endpoint returns 200 ready before shutdown."""
        app, manager = app_with_shutdown

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["shutting_down"] is False

    async def test_new_requests_receive_503_during_shutdown(
        self, app_with_shutdown: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """New requests receive 503 during shutdown drain period."""
        app, manager = app_with_shutdown

        # Start shutdown
        manager.start_shutdown()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Any request should get 503
            response = await client.get("/api/v1/health")

            assert response.status_code == 503

    async def test_in_flight_requests_complete_during_drain(
        self, app_with_shutdown: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """In-flight requests are allowed to complete during drain period."""
        app, manager = app_with_shutdown

        # Create an endpoint that simulates a long-running request
        @app.get("/slow")
        async def slow_endpoint() -> dict[str, str]:
            await asyncio.sleep(0.1)
            return {"status": "completed"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Start a request
            request_task = asyncio.create_task(client.get("/slow"))

            # Wait for request to start processing
            await asyncio.sleep(0.01)

            # Start shutdown
            manager.start_shutdown()

            # Request should complete successfully despite shutdown
            response = await request_task
            assert response.status_code == 200
            assert response.json()["status"] == "completed"


@pytest.mark.integration
@pytest.mark.asyncio
class TestShutdownMiddleware:
    """Integration tests for shutdown middleware that blocks new requests."""

    @pytest.fixture
    async def app_with_middleware(self) -> AsyncGenerator[tuple[FastAPI, ShutdownManager], None]:
        """Create FastAPI app with shutdown middleware."""
        from webapp.shutdown import ShutdownMiddleware

        app = FastAPI()
        manager = ShutdownManager()

        # Add shutdown middleware
        app.add_middleware(ShutdownMiddleware, manager=manager)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        yield app, manager

    async def test_middleware_allows_requests_before_shutdown(
        self, app_with_middleware: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """Middleware allows requests before shutdown starts."""
        app, manager = app_with_middleware

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    async def test_middleware_blocks_new_requests_during_shutdown(
        self, app_with_middleware: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """Middleware blocks new requests during shutdown."""
        app, manager = app_with_middleware

        # Start shutdown
        manager.start_shutdown()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

            assert response.status_code == 503
            data = response.json()
            assert data["detail"] == "Service shutting down"

    async def test_middleware_tracks_in_flight_requests(
        self, app_with_middleware: tuple[FastAPI, ShutdownManager]
    ) -> None:
        """Middleware increments/decrements in-flight request counter."""
        app, manager = app_with_middleware

        assert manager.in_flight_requests == 0

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make a request
            await client.get("/test")

        # Counter should be back to 0 after request completes
        assert manager.in_flight_requests == 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseShutdownIntegration:
    """Integration tests for database cleanup during shutdown."""

    async def test_shutdown_disposes_database_engine(self) -> None:
        """Shutdown properly disposes of database engine."""
        from sqlalchemy.ext.asyncio import create_async_engine

        from webapp.shutdown import shutdown_database

        # Create a real async engine (in-memory SQLite)
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Verify it's usable
        async with engine.begin() as conn:
            result = await conn.execute("SELECT 1")
            assert result.fetchone() == (1,)

        # Shutdown should dispose the engine
        await shutdown_database(engine)

        # Engine should be disposed
        # Attempting to use it should fail
        with pytest.raises((InvalidRequestError, OperationalError)):
            async with engine.begin() as conn:
                await conn.execute("SELECT 1")


@pytest.mark.integration
@pytest.mark.asyncio
class TestSignalHandlerIntegration:
    """Integration tests for signal handler registration."""

    async def test_signal_handlers_trigger_shutdown(self) -> None:
        """SIGTERM/SIGINT handlers trigger graceful shutdown."""
        from webapp.shutdown import handle_shutdown_signal, register_signal_handlers

        manager = ShutdownManager()

        # Register handlers
        register_signal_handlers(manager)

        assert manager.is_shutting_down is False

        # Simulate signal
        handle_shutdown_signal(manager, signal.SIGTERM, None)

        assert manager.is_shutting_down is True
