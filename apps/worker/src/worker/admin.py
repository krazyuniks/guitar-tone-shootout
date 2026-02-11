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
from worker.db import get_session
from worker.schemas import JobDetail, JobSummary

# Create FastAPI app for admin endpoints
app = FastAPI(title="GTS Worker Admin API", version="1.0.0")

# Track worker start time for uptime calculation
_worker_start_time = time.monotonic()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting a database session.

    This dependency can be overridden in tests by using:
        app.dependency_overrides[get_db_session] = test_session_factory

    In tests, if WorkerSettings cannot be loaded (missing env vars),
    falls back to using the in-memory SQLite database. The test fixtures
    register an engine under "sqlite+aiosqlite:///:memory:", so we need
    to check for that key and also register it under the converted key
    to ensure async_session_factory finds it.

    For tests that don't properly set up the database fixtures, we create
    the tables automatically in the test database.

    Yields:
        AsyncSession: Database session with active transaction
    """
    try:
        settings = WorkerSettings()  # type: ignore[call-arg]
        database_url = settings.database_url
        is_test = False
    except Exception:
        # In tests, the conftest registers an engine under the :memory: key,
        # but async_session_factory converts :memory: to shared cache URL
        # before checking the cache. So we need to copy the registration.
        from worker.db import _engine_cache, register_engine

        memory_key = "sqlite+aiosqlite:///:memory:"
        shared_cache_key = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

        # If engine is registered under :memory: key, also register under
        # the shared cache key so async_session_factory can find it
        if memory_key in _engine_cache and shared_cache_key not in _engine_cache:
            register_engine(shared_cache_key, _engine_cache[memory_key])

        database_url = "sqlite+aiosqlite:///:memory:"
        is_test = True

    async with get_session(database_url) as session:
        # In tests, create tables if they don't exist (for tests that don't
        # use db_engine fixture)
        if is_test:
            from sqlalchemy import inspect

            from webapp.adapters.persistence.models.base import Base

            # Check if tables exist by trying to query; if it fails, create them
            def check_and_create_tables(sync_conn):
                inspector = inspect(sync_conn)
                tables = inspector.get_table_names()
                if "jobs" not in tables:
                    Base.metadata.create_all(sync_conn)

            conn = await session.connection()
            await conn.run_sync(check_and_create_tables)

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
