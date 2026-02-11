"""GTS Worker - TaskIQ broker and job definitions.

This module provides the TaskIQ broker configuration and job handlers.
"""

import os

from taskiq_redis import ListQueueBroker

from worker.config import WorkerSettings

# Create broker using settings from environment
# For testing/webapp container without full worker env, use a placeholder URL
# The actual worker container will have the real REDIS_URL
try:
    settings = WorkerSettings()
    redis_url = settings.redis_url
except Exception:
    # Fallback for testing environment (webapp container) - use placeholder
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

broker = ListQueueBroker(redis_url)

# Store the Redis URL for testing verification
broker._redis_url = redis_url  # type: ignore[attr-defined]


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
from worker.jobs.source_sync import handle_source_sync  # noqa: E402, F401
