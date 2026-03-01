"""Integration tests for /api/jobs/ endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.job import Job
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)
from webapp.api.v1.jobs import router, set_session_override, set_user_override

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with jobs router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_returns_job_status(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/{id} returns job status."""
    repo = SQLAlchemyJobRepository(db_session)

    job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.RUNNING,
        progress=50,
        message="Processing audio...",
    )

    async with db_session.begin():
        await repo.save(job)

    response = await authenticated_client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["status"] == "running"
    assert data["progress"] == 50
    assert data["message"] == "Processing audio..."


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_returns_404_for_missing(
    authenticated_client: AsyncClient,
) -> None:
    """Test GET /api/jobs/{id} returns 404 for non-existent job."""
    response = await authenticated_client.get(f"/api/jobs/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_returns_404_for_other_users_job(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test GET /api/jobs/{id} returns 404 for other user's job."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create another user and their job
    other_user = User(username="other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_job = Job(
        user_id=other_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )

    async with db_session.begin():
        await repo.save(other_job)

    # Try to access other user's job
    response = await authenticated_client.get(f"/api/jobs/{other_job.id}")

    # Returns 404 to avoid leaking existence
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_requires_authentication(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/{id} requires authentication."""
    repo = SQLAlchemyJobRepository(db_session)

    job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )

    async with db_session.begin():
        await repo.save(job)

    # Create client without auth override
    set_session_override(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job.id}")

        assert response.status_code == 401

    set_session_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_user_jobs_returns_users_jobs(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/ returns user's jobs."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs for test user
    job1 = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )
    job2 = Job(
        user_id=test_user.id,
        job_type=JobType.VIDEO_COMPOSE,
    )

    async with db_session.begin():
        await repo.save(job1)
        await repo.save(job2)

    response = await authenticated_client.get("/api/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    job_ids = {j["id"] for j in data}
    assert str(job1.id) in job_ids
    assert str(job2.id) in job_ids


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_user_jobs_does_not_return_other_users_jobs(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/ does not return other users' jobs."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create job for test user
    user_job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )
    async with db_session.begin():
        await repo.save(user_job)

    # Create another user and their job
    other_user = User(username="other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_job = Job(
        user_id=other_user.id,
        job_type=JobType.GEAR_SYNC,
    )
    async with db_session.begin():
        await repo.save(other_job)

    response = await authenticated_client.get("/api/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(user_job.id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_user_jobs_filters_by_status(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/?status=running filters by status."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different statuses
    pending = Job(user_id=test_user.id, status=JobStatus.PENDING)
    running = Job(user_id=test_user.id, status=JobStatus.RUNNING)
    completed = Job(user_id=test_user.id, status=JobStatus.COMPLETED)

    async with db_session.begin():
        await repo.save(pending)
        await repo.save(running)
        await repo.save(completed)

    response = await authenticated_client.get("/api/jobs/?status=running")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "running"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_user_jobs_filters_by_job_type(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/?job_type=audio_processing filters by type."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different types
    audio = Job(user_id=test_user.id, job_type=JobType.AUDIO_PROCESSING)
    video = Job(user_id=test_user.id, job_type=JobType.VIDEO_COMPOSE)

    async with db_session.begin():
        await repo.save(audio)
        await repo.save(video)

    response = await authenticated_client.get("/api/jobs/?job_type=audio_processing")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_type"] == "audio_processing"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_includes_timestamps(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test GET /api/jobs/{id} includes created_at and updated_at."""
    repo = SQLAlchemyJobRepository(db_session)

    job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )

    async with db_session.begin():
        await repo.save(job)

    response = await authenticated_client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    data = response.json()
    assert "created_at" in data
    assert "updated_at" in data
