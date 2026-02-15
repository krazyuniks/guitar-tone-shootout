"""Graceful shutdown handling for the FastAPI webapp.

Provides:
- ShutdownManager: State tracking for shutdown lifecycle
- ShutdownMiddleware: Blocks new requests during drain period
- Signal handlers: SIGTERM/SIGINT trigger graceful shutdown
- Lifespan integration: FastAPI context manager for startup/shutdown
- Health endpoint: Returns 503 during shutdown for nginx routing
"""

import asyncio
import contextlib
import logging
import signal
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ShutdownManager:
    """Manages graceful shutdown state and coordination.

    Tracks:
    - Shutdown state (ready vs shutting_down)
    - In-flight request counter
    - Drain timeout configuration
    """

    def __init__(self, drain_timeout: float = 30.0) -> None:
        """Initialize shutdown manager.

        Args:
            drain_timeout: Maximum seconds to wait for in-flight requests
        """
        self.drain_timeout = drain_timeout
        self.is_shutting_down = False
        self.in_flight_requests = 0
        self._drain_event = asyncio.Event()

    def start_shutdown(self) -> None:
        """Mark shutdown as started."""
        self.is_shutting_down = True
        logger.info("Shutdown initiated")

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests.

        Returns:
            True if ready, False if shutting down
        """
        return not self.is_shutting_down

    def increment_in_flight(self) -> None:
        """Increment in-flight request counter."""
        self.in_flight_requests += 1

    def decrement_in_flight(self) -> None:
        """Decrement in-flight request counter.

        Signals drain event if counter reaches zero.
        """
        self.in_flight_requests -= 1
        if self.in_flight_requests == 0:
            self._drain_event.set()

    async def wait_for_in_flight(self) -> None:
        """Wait for all in-flight requests to complete.

        Respects drain_timeout. May raise asyncio.TimeoutError
        if timeout is exceeded.
        """
        if self.in_flight_requests == 0:
            logger.info("No in-flight requests, skipping drain period")
            return

        logger.info(
            f"Draining {self.in_flight_requests} in-flight requests "
            f"(timeout: {self.drain_timeout}s)"
        )

        try:
            await asyncio.wait_for(
                self._drain_event.wait(),
                timeout=self.drain_timeout,
            )
        except TimeoutError:
            logger.warning(
                f"Drain timeout exceeded with {self.in_flight_requests} requests still in flight"
            )
            raise


class ShutdownMiddleware(BaseHTTPMiddleware):
    """Middleware that blocks new requests during shutdown.

    Also tracks in-flight request count.
    """

    def __init__(self, app: Any, manager: ShutdownManager | None = None) -> None:
        """Initialize middleware with shutdown manager.

        Args:
            app: ASGI application
            manager: Shutdown manager instance (optional, can be accessed from request.app.state)
        """
        super().__init__(app)
        self._manager = manager

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request or return 503 if shutting down.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response from handler or 503 Service Unavailable
        """
        # Get manager from constructor or app.state
        manager = self._manager or getattr(request.app.state, "shutdown_manager", None)

        # If no manager is available, allow the request through
        if manager is None:
            return await call_next(request)

        # Health endpoints must remain accessible during shutdown
        # so load balancers can detect the shutdown state
        if manager.is_shutting_down and not request.url.path.startswith("/health"):
            return JSONResponse(
                status_code=503,
                content={"detail": "Service shutting down"},
            )

        # Track in-flight requests
        manager.increment_in_flight()
        try:
            response = await call_next(request)
            return response
        finally:
            manager.decrement_in_flight()


def handle_shutdown_signal(
    manager: ShutdownManager,
    signum: int,
    frame: Any,
) -> None:
    """Handle SIGTERM/SIGINT by starting graceful shutdown.

    Args:
        manager: Shutdown manager instance
        signum: Signal number (SIGTERM or SIGINT)
        frame: Signal frame (unused)
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name}, initiating graceful shutdown")
    manager.start_shutdown()


def register_signal_handlers(manager: ShutdownManager) -> None:
    """Register signal handlers for SIGTERM and SIGINT.

    Args:
        manager: Shutdown manager instance

    Note:
        Signal handlers can only be registered in the main thread.
        This function silently skips registration if called from a non-main thread
        (e.g., during testing with TestClient).
    """
    # Use functools.partial to bind manager to handler
    import threading
    from functools import partial

    # Only register signal handlers in the main thread
    if threading.current_thread() is not threading.main_thread():
        logger.debug("Skipping signal handler registration (not in main thread)")
        return

    handler = partial(handle_shutdown_signal, manager)
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


async def get_health_status(manager: ShutdownManager) -> dict[str, Any]:
    """Get health status for readiness endpoint.

    Args:
        manager: Shutdown manager instance

    Returns:
        Health status dict with status and shutting_down flag
    """
    if manager.is_shutting_down:
        return {
            "status": "unavailable",
            "shutting_down": True,
        }
    else:
        return {
            "status": "ready",
            "shutting_down": False,
        }


async def shutdown_database(engine: Any) -> None:
    """Dispose of database engine and close connection pool.

    Args:
        engine: SQLAlchemy async engine
    """
    logger.info("Closing database connection pool")
    await engine.dispose()
    logger.info("Database connections closed")


async def perform_shutdown(manager: ShutdownManager, engine: Any) -> None:
    """Perform complete graceful shutdown sequence.

    Args:
        manager: Shutdown manager instance
        engine: SQLAlchemy async engine
    """
    start_time = time.time()

    # Wait for in-flight requests (timeout logged by wait_for_in_flight)
    with contextlib.suppress(TimeoutError):
        await manager.wait_for_in_flight()

    # Clean up database
    await shutdown_database(engine)

    elapsed = time.time() - start_time
    logger.info(f"Graceful shutdown complete (elapsed: {elapsed:.2f}s)")


def create_lifespan() -> Any:
    """Create FastAPI lifespan context manager.

    Returns:
        Async context manager for FastAPI lifespan events
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, Any], None]:
        """Lifespan context manager for FastAPI.

        Startup:
        - Create ShutdownManager
        - Register signal handlers
        - Store manager in app.state

        Shutdown:
        - Perform graceful shutdown

        Args:
            app: FastAPI application instance

        Yields:
            dict: State dict with shutdown_manager
        """
        # Startup
        manager = ShutdownManager()
        register_signal_handlers(manager)

        # Store in app.state for access from middleware/endpoints
        app.state.shutdown_manager = manager

        # Get database engine from session factory
        from webapp.dependencies import _session_factory

        engine = None
        if _session_factory is not None:
            # Extract engine from session factory
            engine = _session_factory.kw.get("bind")

        logger.info("FastAPI startup complete")

        # Yield state dict back to FastAPI
        yield {"shutdown_manager": manager}

        # Shutdown
        logger.info("FastAPI shutdown started")
        if engine is not None:
            await perform_shutdown(manager, engine)
        else:
            logger.warning("No database engine found, skipping database shutdown")

    return lifespan
