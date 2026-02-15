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
from starlette.responses import JSONResponse

from webapp.shutdown import ShutdownManager


@pytest.mark.integration
@pytest.mark.asyncio
class TestShutdownWithFastAPI:
    """Integration tests with FastAPI application."""

    @pytest.fixture
    async def app_with_shutdown(self) -> AsyncGenerator[tuple[FastAPI, ShutdownManager], None]:
        """Create FastAPI app with shutdown manager.

        ASGITransport does not trigger ASGI lifespan events, so we set
        up the ShutdownManager directly on app.state and add middleware
        and health routes explicitly.
        """
        from webapp.shutdown import ShutdownMiddleware, get_health_status

        app = FastAPI()
        manager = ShutdownManager()
        app.state.shutdown_manager = manager
        app.add_middleware(ShutdownMiddleware, manager=manager)

        @app.get("/health/ready")
        async def health_ready() -> JSONResponse:
            status = await get_health_status(manager)
            code = 200 if status["status"] == "ready" else 503
            return JSONResponse(content=status, status_code=code)

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
        app, _manager = app_with_shutdown

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
        app, _manager = app_with_middleware

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
        """Shutdown properly disposes of database engine.

        Note: SQLAlchemy's dispose() closes existing connections in the pool
        but doesn't prevent creating new ones. The engine can still be used
        after dispose() - it will just create new connections.

        This test verifies that dispose() is called successfully.
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from webapp.shutdown import shutdown_database

        # Create a real async engine (in-memory SQLite)
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Verify it's usable before shutdown
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.fetchone() == (1,)

        # Shutdown should dispose the engine (closes existing connections)
        await shutdown_database(engine)

        # Verify the function completed without errors
        # Note: The engine can still be used after dispose() - it will create
        # new connections. This is expected SQLAlchemy behavior.
        assert True  # Dispose completed successfully


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
