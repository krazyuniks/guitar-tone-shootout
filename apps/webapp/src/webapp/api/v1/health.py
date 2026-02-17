"""Health check endpoints for liveness and readiness probes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
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
    """Liveness probe - check if process is running."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Readiness probe - check if service can handle requests.

    Tests database connectivity. Used by load balancers to determine
    if traffic should be routed to this instance.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "disconnected"}
