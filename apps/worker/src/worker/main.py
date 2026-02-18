"""GTS Worker - TaskIQ broker and job definitions.

This module provides the TaskIQ broker configuration and job handlers.
"""

import logging
import logging.handlers
import os

_log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=_log_format)

# Add rotating file handler (same as entrypoint — child processes need their own)
_log_dir = os.path.join(os.getenv("GTS_STORAGE_ROOT", "/app/storage"), "logs")
os.makedirs(_log_dir, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(_log_dir, "worker.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
)
_file_handler.setFormatter(logging.Formatter(_log_format))
logging.getLogger().addHandler(_file_handler)

# Separate error log — WARNING+ only, for monitoring breakage
_error_handler = logging.handlers.RotatingFileHandler(
    os.path.join(_log_dir, "worker-errors.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
)
_error_handler.setFormatter(logging.Formatter(_log_format))
_error_handler.setLevel(logging.WARNING)
logging.getLogger().addHandler(_error_handler)

logging.getLogger("source_t3k.services").setLevel(logging.INFO)
logging.getLogger("source_t3k.adapters.inbound").setLevel(logging.INFO)

from taskiq import InMemoryBroker, SimpleRetryMiddleware  # noqa: E402
from taskiq_redis import ListQueueBroker  # noqa: E402

from worker.config import WorkerSettings  # noqa: E402


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
        broker = ListQueueBroker(redis_url).with_middlewares(
            SimpleRetryMiddleware(default_retry_count=0),
        )
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
from worker.jobs import (  # noqa: E402, F401
    handle_shootout_audio_job,
    handle_shootout_job,
    handle_shootout_master_job,
)
from worker.jobs.source_sync import handle_source_sync  # noqa: E402, F401
