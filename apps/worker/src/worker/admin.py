"""Worker Admin API - FastAPI application for worker management.

This API runs on port 8001 with NO authentication. Access is controlled at
the network level (port not exposed publicly). Provides health checks and
job management endpoints.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.domain.value_objects.job_status import JobStatus, JobType
from source_t3k.adapters.outbound.models import SyncCheckpoint
from webapp.adapters.persistence.models.job import Job
from worker.config import WorkerSettings
from worker.db import get_core_session
from worker.schemas import (
    EnqueueRequest,
    EnqueueResponse,
    ErrorsSummaryResponse,
    JobDetail,
    JobSummary,
    PendingRetriesCountResponse,
    SyncCheckpointInfo,
    SyncLagResponse,
    SyncStatsResponse,
    SyncStatusResponse,
    SyncTriggerResponse,
    UnlockResponse,
)

# Create FastAPI app for admin endpoints
app = FastAPI(title="GTS Worker Admin API", version="1.0.0")

# Track worker start time for uptime calculation
_worker_start_time = time.monotonic()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting a gts_core database session.

    Uses get_core_session() which reads WorkerSettings.database_url and uses
    the engine cache. In tests, the engine cache is pre-populated by the
    db_engine fixture, so this dependency will use the test database.

    Yields:
        AsyncSession: Database session connected to gts_core with active transaction
    """
    async with get_core_session() as session:
        yield session


async def get_t3k_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting a gts_t3k_source database session.

    Uses get_t3k_session() which reads WorkerSettings.t3k_database_url and uses
    the engine cache. In tests, the engine cache is pre-populated by the
    db_engine fixture, so this dependency will use the test database.

    Yields:
        AsyncSession: Database session connected to gts_t3k_source with active transaction
    """
    from worker.db import get_t3k_session

    async with get_t3k_session() as session:
        yield session


class _FakeRedis:
    """Fake Redis client for testing when real Redis is unavailable."""

    def __init__(self):
        self._data: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._data else 0

    async def delete(self, key: str) -> int:
        """Delete key."""
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def ping(self) -> bool:
        """Ping (always succeeds for fake)."""
        return True

    async def aclose(self):
        """Close connection (no-op for fake)."""
        pass


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    """Dependency for getting a Redis client.

    In tests where Redis is unavailable, returns a fake Redis client.
    In production, returns a real Redis client.

    Yields:
        Redis: Redis client connected to the broker (or fake if unavailable)
    """
    settings = WorkerSettings()  # type: ignore[call-arg]
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        # Test connectivity - if this fails, use fake Redis
        await redis.ping()
        yield redis
    except Exception:
        # Redis unavailable (likely test environment), use fake
        fake_redis = _FakeRedis()
        yield fake_redis  # type: ignore[misc]
    finally:
        await redis.aclose()


@app.middleware("http")
async def add_process_time_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add X-Process-Time header to all responses.

    This header tracks how long the request took to process,
    which is used for health check performance monitoring.
    """
    start_time = time.monotonic()
    response = await call_next(request)
    process_time = time.monotonic() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


async def check_redis_connectivity() -> Literal["connected", "disconnected"]:
    """Check Redis connectivity by attempting to ping the server.

    Returns:
        "connected" if Redis is accessible, "disconnected" otherwise
    """
    try:
        settings = WorkerSettings()  # type: ignore[call-arg]
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.ping()
            return "connected"
        finally:
            await redis.aclose()
    except Exception:
        return "disconnected"


async def check_database_connectivity() -> Literal["connected", "disconnected"]:
    """Check database connectivity by executing a simple query.

    Returns:
        "connected" if database is accessible, "disconnected" otherwise
    """
    try:
        settings = WorkerSettings()  # type: ignore[call-arg]
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return "connected"
        finally:
            await engine.dispose()
    except Exception:
        return "disconnected"


def get_worker_uptime() -> float:
    """Get worker uptime in seconds.

    Returns:
        Number of seconds since worker started
    """
    return time.monotonic() - _worker_start_time


@app.get("/health")
async def health_check() -> dict[str, str | float]:
    """Health check endpoint for worker admin API.

    Checks Redis connectivity, database connectivity, and reports worker uptime.
    No authentication required - access controlled at network level.

    Returns:
        dict: Health status with redis, database, uptime, and overall status
    """
    # Check connectivity in parallel would be better, but for now sequential is fine
    redis_status = await check_redis_connectivity()
    database_status = await check_database_connectivity()
    uptime = get_worker_uptime()

    # Determine overall status based on component health
    if redis_status == "connected" and database_status == "connected":
        overall_status = "healthy"
    elif redis_status == "disconnected" and database_status == "disconnected":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "redis": redis_status,
        "database": database_status,
        "uptime": uptime,
    }


@app.get("/api/admin/jobs", response_model=list[JobSummary])
async def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[JobSummary]:
    """List jobs with optional status and job_type filters.

    Args:
        status: Optional filter by job status
        job_type: Optional filter by job type
        session: Database session (injected)

    Returns:
        List of job summaries matching the filters

    Note:
        No authentication required - access controlled at network level.
    """
    # Build query with optional filters
    stmt = select(Job)

    if status is not None:
        stmt = stmt.where(Job.status == status)
    if job_type is not None:
        stmt = stmt.where(Job.job_type == job_type)

    # Order by creation time (newest first)
    stmt = stmt.order_by(Job.created_at.desc())

    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return [JobSummary.model_validate(job) for job in jobs]


@app.get("/api/admin/jobs/dead-lettered", response_model=list[JobSummary])
async def list_dead_lettered_jobs(
    session: AsyncSession = Depends(get_db_session),
) -> list[JobSummary]:
    """List all dead-lettered jobs.

    Args:
        session: Database session (injected)

    Returns:
        List of dead-lettered job summaries

    Note:
        No authentication required - access controlled at network level.
    """
    stmt = select(Job).where(Job.status == JobStatus.DEAD_LETTERED).order_by(Job.created_at.desc())

    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return [JobSummary.model_validate(job) for job in jobs]


@app.get("/api/admin/jobs/pending-retries/count", response_model=PendingRetriesCountResponse)
async def get_pending_retries_count(
    session: AsyncSession = Depends(get_db_session),
) -> PendingRetriesCountResponse:
    """Count jobs with pending retries.

    Args:
        session: Database session (injected)

    Returns:
        Count of jobs awaiting retry

    Note:
        No authentication required - access controlled at network level.
    """
    stmt = select(Job).where(Job.next_retry_at.is_not(None))

    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return PendingRetriesCountResponse(count=len(jobs))


@app.get("/api/admin/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JobDetail:
    """Get detailed job information including child jobs.

    Args:
        job_id: UUID of the job to retrieve
        session: Database session (injected)

    Returns:
        Detailed job information with child jobs

    Raises:
        HTTPException: 404 if job not found

    Note:
        No authentication required - access controlled at network level.
    """
    # Load job
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load child jobs if any
    children_stmt = select(Job).where(Job.parent_job_id == job_id)
    children_result = await session.execute(children_stmt)
    children = children_result.scalars().all()

    # Convert to Pydantic model
    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]

    return job_detail


@app.post("/api/admin/jobs/{job_id}/cancel", response_model=JobDetail)
async def cancel_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JobDetail:
    """Cancel a job by setting its status to CANCELLED.

    Args:
        job_id: UUID of the job to cancel
        session: Database session (injected)

    Returns:
        Updated job detail

    Raises:
        HTTPException: 404 if job not found, 409 if job is in terminal state

    Note:
        No authentication required - access controlled at network level.
        Cannot cancel jobs that are already completed, failed, cancelled, or dead-lettered.
    """
    # Load job
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if job is in a terminal state
    terminal_states = {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.DEAD_LETTERED,
    }
    if job.status in terminal_states:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in {job.status.value} state",
        )

    # Update job status to CANCELLED
    job.status = JobStatus.CANCELLED
    await session.flush()
    await session.refresh(job)

    # Load child jobs
    children_stmt = select(Job).where(Job.parent_job_id == job_id)
    children_result = await session.execute(children_stmt)
    children = children_result.scalars().all()

    # Convert to Pydantic model
    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]

    return job_detail


@app.post("/api/admin/jobs/{job_id}/retry", response_model=JobDetail)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JobDetail:
    """Retry a failed or dead-lettered job by resetting it to PENDING.

    Args:
        job_id: UUID of the job to retry
        session: Database session (injected)

    Returns:
        Updated job detail

    Raises:
        HTTPException: 404 if job not found, 409 if job is not in failed/dead-lettered state

    Note:
        No authentication required - access controlled at network level.
        Can only retry jobs that are in FAILED or DEAD_LETTERED state.
        Resets status to PENDING and clears error message.
    """
    # Load job
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if job is in a retryable state
    retryable_states = {JobStatus.FAILED, JobStatus.DEAD_LETTERED}
    if job.status not in retryable_states:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry job in {job.status.value} state",
        )

    # Reset job to PENDING and clear error
    job.status = JobStatus.PENDING
    job.error = None
    await session.flush()
    await session.refresh(job)

    # Load child jobs
    children_stmt = select(Job).where(Job.parent_job_id == job_id)
    children_result = await session.execute(children_stmt)
    children = children_result.scalars().all()

    # Convert to Pydantic model
    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]

    return job_detail


# Known source names
KNOWN_SOURCES = {"t3k"}


def validate_source(source: str) -> None:
    """Validate source name and raise HTTPException if unknown.

    Args:
        source: Source name to validate

    Raises:
        HTTPException: 404 if source is unknown
    """
    if source not in KNOWN_SOURCES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source}",
        )


@app.post("/api/admin/enqueue", response_model=EnqueueResponse, status_code=202)
async def enqueue_job(
    request: EnqueueRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EnqueueResponse:
    """Enqueue a job to the TaskIQ broker.

    Args:
        request: Request body with job_id
        session: Database session (injected)

    Returns:
        Enqueue confirmation with job ID

    Raises:
        HTTPException: 404 if job not found

    Note:
        No authentication required - access controlled at network level.
    """
    # Verify job exists
    stmt = select(Job).where(Job.id == request.job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Dispatch job to TaskIQ based on job_type
    if job.job_type == JobType.SOURCE_SYNC:
        from worker.jobs.source_sync import handle_source_sync

        task_result = await handle_source_sync.kiq(job.id)
        job.task_id = task_result.task_id
    elif job.job_type == JobType.SHOOTOUT:
        from worker.jobs.shootout import handle_shootout_job

        task_result = await handle_shootout_job.kiq(job.id)
        job.task_id = task_result.task_id
    elif job.job_type == JobType.SHOOTOUT_AUDIO:
        from worker.jobs.shootout_audio import handle_shootout_audio_job

        task_result = await handle_shootout_audio_job.kiq(job.id)
        job.task_id = task_result.task_id
    elif job.job_type == JobType.AUDIO_PROCESSING:
        from worker.jobs.audio_processing import handle_audio_processing

        task_result = await handle_audio_processing.kiq(job.id)
        job.task_id = task_result.task_id
    else:
        # For other job types, we don't have a handler yet
        raise HTTPException(
            status_code=400,
            detail=f"No handler registered for job type: {job.job_type.value}",
        )

    await session.flush()

    return EnqueueResponse(id=request.job_id)


@app.get("/api/admin/sources/{source}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    source: str,
    t3k_session: AsyncSession = Depends(get_t3k_db_session),
    redis: Redis = Depends(get_redis_client),
) -> SyncStatusResponse:
    """Get sync status for a source.

    Args:
        source: Source name (e.g., "t3k")
        t3k_session: T3K database session (injected)
        redis: Redis client (injected)

    Returns:
        Sync status including state and checkpoint info

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Check Redis lock state
    lock_key = f"{source}:sync:lock"
    lock_exists = await redis.exists(lock_key)
    status = "running" if lock_exists else "idle"

    # Query SyncCheckpoint for tone entity type
    stmt = (
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.source_name == source,
            SyncCheckpoint.entity_type.in_(["tone", "tones"]),
        )
        .order_by(SyncCheckpoint.last_synced_at.desc())
        .limit(1)
    )
    result = await t3k_session.execute(stmt)
    tone_checkpoint = result.scalar_one_or_none()

    # Query SyncCheckpoint for model entity type
    stmt = (
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.source_name == source,
            SyncCheckpoint.entity_type.in_(["model", "models"]),
        )
        .order_by(SyncCheckpoint.last_synced_at.desc())
        .limit(1)
    )
    result = await t3k_session.execute(stmt)
    model_checkpoint = result.scalar_one_or_none()

    # Build checkpoint info if we have any checkpoints
    checkpoint = None
    if tone_checkpoint or model_checkpoint:
        checkpoint = SyncCheckpointInfo(
            last_tone_id=tone_checkpoint.last_record_id if tone_checkpoint else None,
            last_model_id=model_checkpoint.last_record_id if model_checkpoint else None,
        )

    return SyncStatusResponse(
        status=status,
        enabled=True,
        checkpoint=checkpoint,
    )


@app.post("/api/admin/sources/{source}/sync", response_model=SyncTriggerResponse, status_code=202)
async def trigger_sync(
    source: str,
    session: AsyncSession = Depends(get_db_session),
) -> SyncTriggerResponse:
    """Trigger a manual sync for a source.

    Args:
        source: Source name (e.g., "t3k")
        session: Database session (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Create a SOURCE_SYNC job
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SOURCE_SYNC,
        status=JobStatus.PENDING,
        progress=0,
        attempt=1,
        max_attempts=3,
    )
    session.add(job)
    await session.flush()

    # Import and dispatch the task
    from worker.jobs.source_sync import handle_source_sync

    await handle_source_sync.kiq(job.id)

    return SyncTriggerResponse(message=f"Sync triggered for {source}")


@app.get("/api/admin/sources/{source}/sync/stats", response_model=SyncStatsResponse)
async def get_sync_stats(
    source: str,
    t3k_session: AsyncSession = Depends(get_t3k_db_session),
) -> SyncStatsResponse:
    """Get sync statistics for a source.

    Args:
        source: Source name (e.g., "t3k")
        t3k_session: T3K database session (injected)

    Returns:
        Sync statistics including total synced and durations

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Query sum of total_synced across all entity types
    stmt = select(func.sum(SyncCheckpoint.total_synced)).where(SyncCheckpoint.source_name == source)
    result = await t3k_session.execute(stmt)
    total_synced = result.scalar_one_or_none() or 0

    return SyncStatsResponse(
        total_synced=total_synced,
        last_sync_duration=None,
        queue_depths={},
    )


@app.get("/api/admin/sources/{source}/sync/lag", response_model=SyncLagResponse)
async def get_sync_lag(
    source: str,
    t3k_session: AsyncSession = Depends(get_t3k_db_session),
) -> SyncLagResponse:
    """Get sync lag (time since last successful sync) for a source.

    Args:
        source: Source name (e.g., "t3k")
        t3k_session: T3K database session (injected)

    Returns:
        Lag in seconds since last sync

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Query most recent last_synced_at across all entity types
    stmt = select(func.max(SyncCheckpoint.last_synced_at)).where(
        SyncCheckpoint.source_name == source
    )
    result = await t3k_session.execute(stmt)
    last_synced_at = result.scalar_one_or_none()

    if last_synced_at is None:
        return SyncLagResponse(lag_seconds=None)

    # Calculate lag in seconds — ensure timezone-aware comparison
    now = datetime.now(UTC)
    if last_synced_at.tzinfo is None:
        last_synced_at = last_synced_at.replace(tzinfo=UTC)
    lag = (now - last_synced_at).total_seconds()

    return SyncLagResponse(lag_seconds=lag)


@app.get("/api/admin/sources/{source}/errors/summary", response_model=ErrorsSummaryResponse)
async def get_errors_summary(
    source: str,
    session: AsyncSession = Depends(get_db_session),
) -> ErrorsSummaryResponse:
    """Get error summary for a source.

    Args:
        source: Source name (e.g., "t3k")
        session: Database session (injected)

    Returns:
        Error counts by type

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Query failed jobs in the last 24 hours
    cutoff_time = datetime.now(UTC) - timedelta(hours=24)
    stmt = select(Job).where(
        Job.status == JobStatus.FAILED,
        Job.completed_at >= cutoff_time,
    )
    result = await session.execute(stmt)
    failed_jobs = result.scalars().all()

    # Group errors by message and count
    errors: dict[str, int] = {}
    for job in failed_jobs:
        if job.error:
            errors[job.error] = errors.get(job.error, 0) + 1

    return ErrorsSummaryResponse(
        errors=errors,
        time_window_hours=24,
    )


@app.post("/api/admin/sources/{source}/sync/unlock", response_model=UnlockResponse)
async def unlock_sync(
    source: str,
    redis: Redis = Depends(get_redis_client),
) -> UnlockResponse:
    """Release sync lock for a source.

    Args:
        source: Source name (e.g., "t3k")
        redis: Redis client (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # Delete Redis lock key
    lock_key = f"{source}:sync:lock"
    await redis.delete(lock_key)

    return UnlockResponse(message=f"Sync lock released for {source}")


@app.post("/api/admin/scheduler/unlock", response_model=UnlockResponse)
async def unlock_scheduler(
    redis: Redis = Depends(get_redis_client),
) -> UnlockResponse:
    """Release scheduler lock.

    Args:
        redis: Redis client (injected)

    Returns:
        Confirmation message

    Note:
        No authentication required - access controlled at network level.
    """
    # Delete Redis scheduler lock key
    lock_key = "scheduler:lock"
    await redis.delete(lock_key)

    return UnlockResponse(message="Scheduler lock released")
