"""Health check task for worker validation."""

from datetime import UTC, datetime

from app.tasks.broker import broker


@broker.task
async def health_check() -> dict[str, str | bool]:
    """Simple health check task to verify worker is running.

    Returns:
        Dictionary with worker health status and timestamp.
    """
    return {
        "status": "healthy",
        "worker": True,
        "timestamp": datetime.now(UTC).isoformat(),
    }
