"""GTS Worker - TaskIQ broker and job definitions.

This module provides the TaskIQ broker configuration and job handlers.
"""

import os

from taskiq import InMemoryBroker
from taskiq_redis import ListQueueBroker

from worker.config import WorkerSettings


def _create_broker():
    """Create TaskIQ broker, falling back to InMemoryBroker if Redis unavailable.

    In production, uses ListQueueBroker with Redis.
    In tests where Redis is unavailable, uses InMemoryBroker.
    """
    # Get Redis URL from settings or environment
    try:
        settings = WorkerSettings()
        redis_url = settings.redis_url
    except Exception:
        # Fallback for testing environment (webapp container)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Try to create a Redis broker
    try:
        # Test Redis connectivity synchronously during import
        import redis

        r = redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
        r.close()

        # Redis available, use ListQueueBroker
        broker = ListQueueBroker(redis_url)
        broker._redis_url = redis_url  # type: ignore[attr-defined]
        return broker
    except Exception:
        # Redis unavailable (test environment), use InMemoryBroker
        return InMemoryBroker()


broker = _create_broker()


@broker.task
async def example_task(message: str) -> str:
    """Example task for testing.

    Args:
        message: A test message

    Returns:
        Processed message
    """
    return f"Processed: {message}"


# Import job handlers to register them with the broker
from worker.jobs import handle_shootout_audio_job, handle_shootout_job  # noqa: E402, F401
from worker.jobs.source_sync import (  # noqa: E402, F401
    handle_backfill_downloads,
    handle_source_sync,
)
