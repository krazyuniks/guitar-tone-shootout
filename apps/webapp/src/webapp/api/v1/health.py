"""Health check endpoints for liveness and readiness probes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    This is a placeholder that will be overridden when the router is included
    in the main app with dependency_overrides.
    """
    raise NotImplementedError("Database session dependency not configured")


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Liveness probe - check if process is running.

    This endpoint returns immediately without any I/O operations.
    Used by container orchestration to determine if the process should be restarted.

    Returns:
        dict: Status indicating process is alive
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Readiness probe - check if service can handle requests.

    Tests:
    1. Shutdown state (returns 503 if shutting down)
    2. Database connectivity

    Used by load balancers to determine if traffic should be routed to this instance.

    Args:
        request: FastAPI request object for accessing app state
        response: FastAPI response object for setting status code
        db: Database session

    Returns:
        dict: Status and database connectivity status
    """
    # Check if shutdown is in progress
    shutdown_manager = getattr(request.app.state, "shutdown_manager", None)
    if shutdown_manager and shutdown_manager.is_shutting_down:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "shutting_down": True}

    try:
        # Execute simple query to verify DB connection
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        # Database connection failed
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "disconnected"}
