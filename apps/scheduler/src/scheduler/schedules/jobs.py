"""Scheduled tasks for job monitoring and retry processing.

This module defines scheduled tasks that run periodically to:
- Monitor for stale (crashed) jobs via heartbeat checks
- Process pending retries with exponential backoff
- Update scheduler health and renew distributed lock
- Ensure T3K source sync is running
"""

import os
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from core.domain.value_objects.job_status import JobStatus
from scheduler.db import get_session
from scheduler.lock import DistributedLock
from webapp.adapters.persistence.models.job import Job as JobModel
from worker.jobs.source_sync import handle_source_sync

# Test hooks: allows tests to inject a database engine or session
_test_engine: AsyncEngine | None = None
_test_session: AsyncSession | None = None


class _Schedule:
    """Schedule configuration for TaskIQ.

    Attributes:
        seconds: Interval in seconds
    """

    def __init__(self, seconds: int) -> None:
        """Initialize schedule.

        Args:
            seconds: Interval in seconds
        """
        self.seconds = seconds


async def monitor_stale_jobs(db_engine: AsyncEngine | None = None) -> None:
    """Monitor for stale jobs and mark them as DEAD_LETTERED.

    Finds RUNNING jobs with last_heartbeat older than 2 minutes and marks them
    as DEAD_LETTERED with an error message.

    Args:
        db_engine: Optional database engine (for testing). If None, uses registered engine.
    """
    # Calculate stale threshold (2 minutes ago)
    stale_threshold = datetime.now(UTC) - timedelta(minutes=2)

    async def _do_update(session: AsyncSession) -> None:
        stmt = (
            update(JobModel)
            .where(
                JobModel.status == JobStatus.RUNNING.value,
                JobModel.last_heartbeat < stale_threshold,
            )
            .values(
                status=JobStatus.DEAD_LETTERED,
                error="Stale heartbeat detected: worker failed to update heartbeat within 2 minutes",
                completed_at=datetime.now(UTC),
            )
        )
        await session.execute(stmt)

    # Use test session if available (shares same connection as test)
    if _test_session is not None:
        await _do_update(_test_session)
        return

    # Get database engine
    engine: AsyncEngine
    if db_engine is not None:
        engine = db_engine
    else:
        from scheduler.db import get_registered_engine

        registered = get_registered_engine()
        if registered is not None:
            engine = registered
        else:
            import os

            database_url = os.getenv("DATABASE_URL", "")
            if not database_url:
                msg = "DATABASE_URL environment variable not set"
                raise ValueError(msg)

            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(database_url)

    async with get_session(engine) as session:
        await _do_update(session)


async def process_pending_retries(db_engine: AsyncEngine | None = None) -> None:
    """Process pending retries for FAILED jobs.

    Finds FAILED jobs with:
    - attempt < max_attempts
    - next_retry_at <= now

    Resets them to PENDING status for retry.

    Args:
        db_engine: Optional database engine (for testing). If None, uses registered engine.
    """
    now = datetime.now(UTC)

    async def _do_retry(session: AsyncSession) -> None:
        select_stmt = select(JobModel).where(
            JobModel.status == JobStatus.FAILED.value,
            JobModel.next_retry_at.isnot(None),
            JobModel.next_retry_at <= now,
        )
        result = await session.execute(select_stmt)
        jobs = result.scalars().all()

        eligible_jobs = [j for j in jobs if j.attempt < j.max_attempts]
        for job in eligible_jobs:
            job.status = JobStatus.PENDING
        await session.flush()

    # Use test session if available (shares same connection as test)
    if _test_session is not None:
        await _do_retry(_test_session)
        return

    # Get database engine
    engine: AsyncEngine
    if db_engine is not None:
        engine = db_engine
    else:
        from scheduler.db import get_registered_engine

        registered = get_registered_engine()
        if registered is not None:
            engine = registered
        else:
            import os

            database_url = os.getenv("DATABASE_URL", "")
            if not database_url:
                msg = "DATABASE_URL environment variable not set"
                raise ValueError(msg)

            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(database_url)

    async with get_session(engine) as session:
        await _do_retry(session)


async def scheduler_heartbeat(lock: DistributedLock | None = None) -> None:
    """Update scheduler health and renew distributed lock.

    Args:
        lock: Optional distributed lock instance (for testing). If None, no lock renewal.
    """
    # Renew distributed lock if provided
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
    redis_client = get_redis_client()
    try:
        lock_exists = await redis_client.exists("t3k:sync:lock")

        if lock_exists == 0:
            sync_enabled = os.getenv("T3K_SYNC_ENABLED", "true").lower() == "true"
            if sync_enabled:
                # Import here to avoid circular dependencies
                from uuid import uuid7

                from core.domain.value_objects.job_status import JobType
                from scheduler.db import _engine_cache

                # Get database engine
                engine: AsyncEngine
                if db_engine is not None:
                    engine = db_engine
                else:
                    # Check worker.db cache first (for tests that register there)
                    try:
                        from worker.db import _engine_cache as worker_cache

                        database_url = os.getenv("DATABASE_URL", "")
                        if database_url and database_url in worker_cache:
                            engine = worker_cache[database_url]
                        elif worker_cache:
                            # Use first registered engine from worker cache
                            engine = next(iter(worker_cache.values()))
                        elif database_url in _engine_cache:
                            engine = _engine_cache[database_url]
                        elif _engine_cache:
                            # Use first registered engine from scheduler cache
                            engine = next(iter(_engine_cache.values()))
                        else:
                            # No registered engine, create new one
                            if not database_url:
                                msg = "DATABASE_URL environment variable not set"
                                raise ValueError(msg)

                            from sqlalchemy.ext.asyncio import create_async_engine

                            engine = create_async_engine(database_url)
                    except ImportError:
                        # worker.db not available, use scheduler cache only
                        from scheduler.db import get_registered_engine

                        registered = get_registered_engine()
                        if registered is not None:
                            engine = registered
                        else:
                            database_url = os.getenv("DATABASE_URL", "")
                            if not database_url:
                                msg = "DATABASE_URL environment variable not set"
                                raise ValueError(msg)

                            from sqlalchemy.ext.asyncio import create_async_engine

                            engine = create_async_engine(database_url)

                # Create Job record
                job_id = uuid7()
                async with get_session(engine) as session:
                    job = JobModel(
                        id=job_id,
                        job_type=JobType.SOURCE_SYNC,
                        user_id=None,  # System-initiated job
                        status=JobStatus.PENDING,
                    )
                    session.add(job)
                    await session.flush()

                # Dispatch job
                await handle_source_sync.kiq(job_id)
    finally:
        await redis_client.aclose()


# Attach labels to functions for TaskIQ discovery
monitor_stale_jobs.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
process_pending_retries.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
scheduler_heartbeat.labels = {"schedule": [_Schedule(60)]}  # type: ignore[attr-defined]
ensure_source_sync_running.labels = {"schedule": [_Schedule(300)]}  # type: ignore[attr-defined]
