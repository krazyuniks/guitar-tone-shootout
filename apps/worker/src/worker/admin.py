"""Worker Admin API - FastAPI application for worker management.

This API runs on port 8001 with NO authentication. Access is controlled at
the network level (port not exposed publicly). Provides health checks and
job management endpoints.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from worker.config import WorkerSettings

# Create FastAPI app for admin endpoints
app = FastAPI(title="GTS Worker Admin API", version="1.0.0")

# Track worker start time for uptime calculation
_worker_start_time = time.monotonic()


@app.middleware("http")
async def add_process_time_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add X-Process-Time header to all responses.

    This header tracks how long the request took to process,
    which is used for health check performance monitoring.
    """
    start_time = time.monotonic()
    response = await call_next(request)
    process_time = time.monotonic() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


async def check_redis_connectivity() -> Literal["connected", "disconnected"]:
    """Check Redis connectivity by attempting to ping the server.

    Returns:
        "connected" if Redis is accessible, "disconnected" otherwise
    """
    try:
        settings = WorkerSettings()  # type: ignore[call-arg]
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.ping()
            return "connected"
        finally:
            await redis.aclose()
    except Exception:
        return "disconnected"


async def check_database_connectivity() -> Literal["connected", "disconnected"]:
    """Check database connectivity by executing a simple query.

    Returns:
        "connected" if database is accessible, "disconnected" otherwise
    """
    try:
        settings = WorkerSettings()  # type: ignore[call-arg]
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return "connected"
        finally:
            await engine.dispose()
    except Exception:
        return "disconnected"


def get_worker_uptime() -> float:
    """Get worker uptime in seconds.

    Returns:
        Number of seconds since worker started
    """
    return time.monotonic() - _worker_start_time


@app.get("/health")
async def health_check() -> dict[str, str | float]:
    """Health check endpoint for worker admin API.

    Checks Redis connectivity, database connectivity, and reports worker uptime.
    No authentication required - access controlled at network level.

    Returns:
        dict: Health status with redis, database, uptime, and overall status
    """
    # Check connectivity in parallel would be better, but for now sequential is fine
    redis_status = await check_redis_connectivity()
    database_status = await check_database_connectivity()
    uptime = get_worker_uptime()

    # Determine overall status based on component health
    if redis_status == "connected" and database_status == "connected":
        overall_status = "healthy"
    elif redis_status == "disconnected" and database_status == "disconnected":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "redis": redis_status,
        "database": database_status,
        "uptime": uptime,
    }
