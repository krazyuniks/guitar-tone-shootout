"""Scheduled tasks for job monitoring and retry processing.

This module defines scheduled tasks that run periodically to:
- Monitor for stale (crashed) jobs via heartbeat checks
- Process pending retries with exponential backoff
- Update scheduler health and renew distributed lock
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from core.domain.value_objects.job_status import JobStatus
from scheduler.db import get_session
from scheduler.lock import DistributedLock
from webapp.adapters.persistence.models.job import Job as JobModel

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


# Attach labels to functions for TaskIQ discovery
monitor_stale_jobs.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
process_pending_retries.labels = {"schedule": [_Schedule(120)]}  # type: ignore[attr-defined]
scheduler_heartbeat.labels = {"schedule": [_Schedule(60)]}  # type: ignore[attr-defined]
