"""Integration tests for SHOOTOUT_MASTER enqueue path in worker admin API."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job


@pytest.fixture
def admin_app():
    """Create Worker Admin API app instance for testing."""
    from worker.admin import app

    return app


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Create database session from engine."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.mark.asyncio
async def test_enqueue_shootout_master_job_sets_task_id(
    admin_app,
    db_session: AsyncSession,
) -> None:
    """POST /api/admin/enqueue should dispatch SHOOTOUT_MASTER jobs."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SHOOTOUT_MASTER,
        status=JobStatus.PENDING,
        entity_id=uuid4(),
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=admin_app), base_url="http://test"
    ) as client:
        response = await client.post("/api/admin/enqueue", json={"job_id": str(job.id)})

    assert response.status_code == 202
    assert response.json() == {"id": str(job.id)}

    result = await db_session.execute(select(Job).where(Job.id == job.id))
    queued_job = result.scalar_one()
    assert queued_job.task_id is not None
