"""Integration tests for SHOOTOUT_MASTER enqueue path in worker admin API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def admin_app(db_session: AsyncSession) -> AsyncGenerator:
    """Worker Admin API with dependency overrides for test isolation."""
    from worker.admin import app, get_db_session, get_t3k_db_session

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_t3k_db_session] = override_session
    yield app
    app.dependency_overrides.clear()


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
    await db_session.flush()

    async with AsyncClient(
        transport=ASGITransport(app=admin_app), base_url="http://test"
    ) as client:
        response = await client.post("/api/admin/enqueue", json={"job_id": str(job.id)})

    assert response.status_code == 202
    assert response.json() == {"id": str(job.id)}

    result = await db_session.execute(select(Job).where(Job.id == job.id))
    queued_job = result.scalar_one()
    assert queued_job.task_id is not None
