"""Integration tests for SHOOTOUT_MASTER enqueue path in webapp admin API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def admin_app(db_session: AsyncSession) -> AsyncGenerator:
    """Webapp Admin router mounted on a test FastAPI app with session override."""
    from fastapi import FastAPI

    from webapp.api.admin import _get_db as _admin_get_db
    from webapp.api.admin import router

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[_admin_get_db] = override_session
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_enqueue_shootout_master_job_returns_202(
    admin_app,
    db_session: AsyncSession,
) -> None:
    """POST /api/admin/enqueue dispatches SHOOTOUT_MASTER to pgmq audio_commands queue."""
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
