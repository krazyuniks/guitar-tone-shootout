"""Scheduled tasks for job monitoring and retry processing.

This module defines scheduled tasks that run periodically to:
- Monitor for stale (crashed) jobs via heartbeat checks
- Process pending retries with exponential backoff
- Update scheduler health and renew distributed lock
- Ensure T3K source sync is running
"""

import logging
import os
from datetime import UTC, datetime, timedelta

import httpx
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from core.domain.auth_gate import check_auth_status
from core.domain.value_objects.job_status import JobStatus
from scheduler.db import get_session
from scheduler.lock import DistributedLock

# Test hooks: allows tests to inject a database engine or session
_test_engine: AsyncEngine | None = None
_test_session: AsyncSession | None = None
logger = logging.getLogger(__name__)


class _Schedule:
    """Schedule configuration for TaskIQ.

    Attributes:
        seconds: Interval in seconds
    """

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds


async def monitor_stale_jobs(db_engine: AsyncEngine | None = None) -> None:
    """Monitor for stale jobs and mark them as DEAD_LETTERED.

    Finds RUNNING jobs with last_heartbeat older than 2 minutes and marks them
    as DEAD_LETTERED with an error message.

    Args:
        db_engine: Optional database engine (for testing). If None, uses registered engine.
    """
    stale_threshold = datetime.now(UTC) - timedelta(minutes=2)

    stmt = text("""
        UPDATE jobs SET status = :dead_status, error = :error, completed_at = :now
        WHERE status = :running_status AND last_heartbeat < :threshold
    """)
    params = {
        "dead_status": JobStatus.DEAD_LETTERED.value,
        "error": "Stale heartbeat detected: worker failed to update heartbeat within 2 minutes",
        "running_status": JobStatus.RUNNING.value,
        "threshold": stale_threshold,
        "now": datetime.now(UTC),
    }

    # Use test session if available (shares same connection as test)
    if _test_session is not None:
        await _test_session.execute(stmt, params)
        return

    engine = _resolve_engine(db_engine)
    async with get_session(engine) as session:
        await session.execute(stmt, params)


async def process_pending_retries(db_engine: AsyncEngine | None = None) -> None:
    """Process pending retries for FAILED jobs.

    Finds FAILED jobs with attempt < max_attempts and next_retry_at <= now,
    and resets them to PENDING status for retry.

    Args:
        db_engine: Optional database engine (for testing). If None, uses registered engine.
    """
    now = datetime.now(UTC)

    stmt = text("""
        UPDATE jobs SET status = :pending_status
        WHERE status = :failed_status
          AND next_retry_at IS NOT NULL
          AND next_retry_at <= :now
          AND attempt < max_attempts
    """)
    params = {
        "pending_status": JobStatus.PENDING.value,
        "failed_status": JobStatus.FAILED.value,
        "now": now,
    }

    # Use test session if available (shares same connection as test)
    if _test_session is not None:
        await _test_session.execute(stmt, params)
        return

    engine = _resolve_engine(db_engine)
    async with get_session(engine) as session:
        await session.execute(stmt, params)


async def scheduler_heartbeat(lock: DistributedLock | None = None) -> None:
    """Update scheduler health and renew distributed lock.

    Args:
        lock: Optional distributed lock instance (for testing). If None, no lock renewal.
    """
    if lock is not None:
        await lock.renew()


def get_redis_client() -> redis.Redis:
    """Get Redis client for checking sync locks."""
    from scheduler.config import SchedulerSettings

    settings = SchedulerSettings()
    return redis.from_url(settings.redis_url)


async def ensure_source_sync_running(db_engine: AsyncEngine | None = None) -> None:
    """Ensure T3K source sync is running by checking Redis lock and dispatching if needed.

    Args:
        db_engine: Optional database engine (for testing). If None, uses registered engine.
    """
    # Check auth gate before dispatching sync
    status = check_auth_status(os.getenv("GTS_AUTH_FILE", "/.gts-auth.json"))
    if not status.can_proceed():
        logger.debug("Skipping sync dispatch: auth status is %s", status.value)
        return

    lock_key = "t3k:sync:lock"
    redis_client = get_redis_client()
    try:
        lock_exists = await redis_client.exists(lock_key)
        if lock_exists != 0:
            return

        sync_enabled = os.getenv("T3K_SYNC_ENABLED", "true").lower() == "true"
        if not sync_enabled:
            return

        # Dispatch sync via worker admin API (no worker import needed)
        worker_url = os.getenv("WORKER_ADMIN_URL", "http://worker:8001")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{worker_url}/api/admin/sources/t3k/sync",
                timeout=10.0,
            )
            if response.status_code < 300:
                logger.info("Dispatched T3K source sync via admin API")
            else:
                logger.warning(
                    "Failed to dispatch T3K sync: %d %s",
                    response.status_code,
                    response.text[:200],
                )
    except Exception:
        logger.exception("Error in ensure_source_sync_running")
    finally:
        await redis_client.aclose()


def _resolve_engine(db_engine: AsyncEngine | None) -> AsyncEngine:
    """Resolve database engine from argument, test hook, or registry."""
    if db_engine is not None:
        return db_engine

    from scheduler.db import get_registered_engine

    registered = get_registered_engine()
    if registered is not None:
        return registered

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        msg = "DATABASE_URL environment variable not set"
        raise ValueError(msg)

    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(database_url)


# Attach labels to functions for TaskIQ discovery
monitor_stale_jobs.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
process_pending_retries.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
scheduler_heartbeat.labels = {"schedule": [_Schedule(60)]}  # type: ignore[attr-defined]
ensure_source_sync_running.labels = {"schedule": [_Schedule(300)]}  # type: ignore[attr-defined]
