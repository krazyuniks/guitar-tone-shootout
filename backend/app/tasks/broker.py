"""TaskIQ broker configuration with Redis backend."""

import os

from taskiq import InMemoryBroker
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.core.config import settings


def get_broker() -> ListQueueBroker | InMemoryBroker:
    """Create and configure the TaskIQ broker.

    Uses Redis in normal operation, InMemoryBroker for testing.
    """
    # Use in-memory broker for testing
    if os.environ.get("TESTING"):
        return InMemoryBroker()

    broker = ListQueueBroker(url=settings.redis_url)
    broker.with_result_backend(
        RedisAsyncResultBackend(
            redis_url=settings.redis_url,
            result_ex_time=3600,  # Results expire after 1 hour
        )
    )
    return broker


# Create the broker instance
broker = get_broker()
