"""Worker Admin API - FastAPI application for worker management.

This API runs on port 8001 with NO authentication. Access is controlled at
the network level (port not exposed publicly). Provides health checks and
job management endpoints.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal
from uuid import UUID  # noqa: TC003 - used at runtime for FastAPI parameter parsing

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job
from worker.config import WorkerSettings
from worker.db import get_core_session
from worker.schemas import (
    AuthStatusResponse,
    EnqueueRequest,
    EnqueueResponse,
    ErrorsSummaryResponse,
    JobDetail,
    JobSummary,
    PendingRetriesCountResponse,
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

    # TODO: Actually enqueue to TaskIQ broker
    # For now, just return success

    return EnqueueResponse(id=request.job_id)


@app.get("/api/admin/sources/{source}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(source: str) -> SyncStatusResponse:
    """Get sync status for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Sync status including state and checkpoint info

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # For now, return defaults
    # TODO: Query actual sync state from database or cache
    return SyncStatusResponse(
        status="idle",
        enabled=True,
        checkpoint=None,
    )


@app.post("/api/admin/sources/{source}/sync", response_model=SyncTriggerResponse, status_code=202)
async def trigger_sync(source: str) -> SyncTriggerResponse:
    """Trigger a manual sync for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Confirmation message

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # TODO: Actually trigger sync job
    return SyncTriggerResponse(message=f"Sync triggered for {source}")


@app.get("/api/admin/sources/{source}/sync/stats", response_model=SyncStatsResponse)
async def get_sync_stats(source: str) -> SyncStatsResponse:
    """Get sync statistics for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Sync statistics including total synced and durations

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # For now, return defaults
    # TODO: Query actual stats from SyncCheckpoint table
    return SyncStatsResponse(
        total_synced=0,
        last_sync_duration=None,
        queue_depths={},
    )


@app.get("/api/admin/sources/{source}/sync/lag", response_model=SyncLagResponse)
async def get_sync_lag(source: str) -> SyncLagResponse:
    """Get sync lag (time since last successful sync) for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Lag in seconds since last sync

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # For now, return default
    # TODO: Calculate actual lag from SyncCheckpoint table
    return SyncLagResponse(lag_seconds=None)


@app.get("/api/admin/sources/{source}/errors/summary", response_model=ErrorsSummaryResponse)
async def get_errors_summary(source: str) -> ErrorsSummaryResponse:
    """Get error summary for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Error counts by type

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # For now, return defaults
    # TODO: Query actual errors from database
    return ErrorsSummaryResponse(
        errors={},
        time_window_hours=24,
    )


@app.get("/api/admin/sources/{source}/auth/status", response_model=AuthStatusResponse)
async def get_auth_status(source: str) -> AuthStatusResponse:
    """Get OAuth token validity status for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        OAuth token validity and expiry

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # For now, return defaults
    # TODO: Query actual OAuth token from database
    return AuthStatusResponse(
        valid=False,
        expires_at=None,
    )


@app.post("/api/admin/sources/{source}/sync/unlock", response_model=UnlockResponse)
async def unlock_sync(source: str) -> UnlockResponse:
    """Release sync lock for a source.

    Args:
        source: Source name (e.g., "t3k")

    Returns:
        Confirmation message

    Raises:
        HTTPException: 404 if source is unknown

    Note:
        No authentication required - access controlled at network level.
    """
    validate_source(source)

    # TODO: Actually release sync lock (Redis or database)
    return UnlockResponse(message=f"Sync lock released for {source}")


@app.post("/api/admin/scheduler/unlock", response_model=UnlockResponse)
async def unlock_scheduler() -> UnlockResponse:
    """Release scheduler lock.

    Returns:
        Confirmation message

    Note:
        No authentication required - access controlled at network level.
    """
    # TODO: Actually release scheduler lock (Redis or database)
    return UnlockResponse(message="Scheduler lock released")
