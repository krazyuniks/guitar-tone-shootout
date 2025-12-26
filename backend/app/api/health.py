"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health")


@router.get("")
async def health_check() -> dict[str, str]:
    """Check if the API is running."""
    return {"status": "healthy", "service": "guitar-tone-shootout"}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Check if the API is ready to serve requests.

    TODO: Add database and Redis connectivity checks.
    """
    return {"status": "ready"}
