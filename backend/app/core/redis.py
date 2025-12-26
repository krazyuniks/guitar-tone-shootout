"""Redis client for pub/sub and caching."""

import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings


def get_redis_client() -> Any:
    """Create an async Redis client.

    Returns:
        Async Redis client instance.
    """
    return Redis.from_url(settings.redis_url, decode_responses=True)


# Singleton client for the application
redis_client: Any = get_redis_client()


async def publish_job_progress(
    job_id: str,
    status: str,
    progress: int,
    message: str | None = None,
) -> None:
    """Publish job progress update to Redis pub/sub.

    Args:
        job_id: The job UUID as string.
        status: Current job status.
        progress: Progress percentage (0-100).
        message: Optional status message.
    """
    channel = f"job:{job_id}:progress"
    data = {
        "type": "progress",
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await redis_client.publish(channel, json.dumps(data))


async def subscribe_job_progress(job_id: str) -> Any:
    """Subscribe to job progress updates.

    Args:
        job_id: The job UUID as string.

    Returns:
        Redis pubsub object subscribed to job channel.
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"job:{job_id}:progress")
    return pubsub
