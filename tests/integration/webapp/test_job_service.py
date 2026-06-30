"""Integration tests for JobService status queries and user filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from gts.domain.entities.job import Job
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)
from webapp.services.job_service import JobService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user."""
    user = User(username="otheruser", email="other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_returns_job(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test getting a job by ID returns the job."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create a job
    job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        entity_id=uuid4(),
    )

    async with db_session.begin():
        await repo.save(job)

    # Retrieve job
    retrieved = await service.get_by_id(job.id, job.user_id)

    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.user_id == test_user.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_by_id_returns_none_for_missing(
    db_session: AsyncSession,
) -> None:
    """Test getting a non-existent job returns None."""
    service = JobService(db_session)

    result = await service.get_by_id(uuid4(), uuid4())

    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_by_user_id_filters_by_owner(
    db_session: AsyncSession,
    test_user: User,
    other_user: User,
) -> None:
    """Test getting jobs by user ID only returns user's own jobs."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs for test_user
    job1 = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        entity_id=uuid4(),
    )
    job2 = Job(
        user_id=test_user.id,
        job_type=JobType.VIDEO_COMPOSE,
        entity_id=uuid4(),
    )

    # Create job for other_user
    other_job = Job(
        user_id=other_user.id,
        job_type=JobType.GEAR_SYNC,
        entity_id=uuid4(),
    )

    async with db_session.begin():
        await repo.save(job1)
        await repo.save(job2)
        await repo.save(other_job)

    # Get test_user's jobs
    results = await service.get_by_user_id(test_user.id)

    assert len(results) == 2
    assert all(j.user_id == test_user.id for j in results)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_by_user_id_filters_by_status(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test filtering jobs by status."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different statuses
    pending_job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
    )
    running_job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.RUNNING,
    )
    completed_job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.COMPLETED,
    )

    async with db_session.begin():
        await repo.save(pending_job)
        await repo.save(running_job)
        await repo.save(completed_job)

    # Filter by status
    pending_results = await service.get_by_user_id(test_user.id, status=JobStatus.PENDING)
    running_results = await service.get_by_user_id(test_user.id, status=JobStatus.RUNNING)

    assert len(pending_results) == 1
    assert pending_results[0].status == JobStatus.PENDING

    assert len(running_results) == 1
    assert running_results[0].status == JobStatus.RUNNING


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_by_user_id_filters_by_job_type(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test filtering jobs by job type."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different types
    audio_job = Job(
        user_id=test_user.id,
        job_type=JobType.AUDIO_PROCESSING,
    )
    video_job = Job(
        user_id=test_user.id,
        job_type=JobType.VIDEO_COMPOSE,
    )

    async with db_session.begin():
        await repo.save(audio_job)
        await repo.save(video_job)

    # Filter by type
    audio_results = await service.get_by_user_id(test_user.id, job_type=JobType.AUDIO_PROCESSING)

    assert len(audio_results) == 1
    assert audio_results[0].job_type == JobType.AUDIO_PROCESSING


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_jobs_returns_non_terminal_jobs(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test getting active jobs returns pending, queued, and running jobs."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with various statuses
    pending = Job(user_id=test_user.id, status=JobStatus.PENDING)
    queued = Job(user_id=test_user.id, status=JobStatus.QUEUED)
    running = Job(user_id=test_user.id, status=JobStatus.RUNNING)
    completed = Job(user_id=test_user.id, status=JobStatus.COMPLETED)
    failed = Job(user_id=test_user.id, status=JobStatus.FAILED)

    async with db_session.begin():
        for job in [pending, queued, running, completed, failed]:
            await repo.save(job)

    # Get active jobs
    active = await service.get_active_by_user_id(test_user.id)

    assert len(active) == 3
    active_statuses = {j.status for j in active}
    assert active_statuses == {JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_jobs_by_user_id_returns_count(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test counting jobs for a user."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create three jobs
    for _ in range(3):
        job = Job(user_id=test_user.id, job_type=JobType.AUDIO_PROCESSING)
        async with db_session.begin():
            await repo.save(job)

    count = await service.count_by_user_id(test_user.id)

    assert count == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_jobs_by_user_id_filters_by_status(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test counting jobs filtered by status."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different statuses
    for _ in range(2):
        pending = Job(user_id=test_user.id, status=JobStatus.PENDING)
        async with db_session.begin():
            await repo.save(pending)

    for _ in range(3):
        completed = Job(user_id=test_user.id, status=JobStatus.COMPLETED)
        async with db_session.begin():
            await repo.save(completed)

    pending_count = await service.count_by_user_id(test_user.id, status=JobStatus.PENDING)
    completed_count = await service.count_by_user_id(test_user.id, status=JobStatus.COMPLETED)

    assert pending_count == 2
    assert completed_count == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_by_entity_id_returns_entity_jobs(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test getting all jobs for a specific entity."""
    service = JobService(db_session)
    repo = SQLAlchemyJobRepository(db_session)

    entity_id = uuid4()

    # Create jobs for entity
    job1 = Job(user_id=test_user.id, entity_id=entity_id)
    job2 = Job(user_id=test_user.id, entity_id=entity_id)

    # Create job for different entity
    other_job = Job(user_id=test_user.id, entity_id=uuid4())

    async with db_session.begin():
        await repo.save(job1)
        await repo.save(job2)
        await repo.save(other_job)

    # Get jobs for entity
    results = await service.get_by_entity_id(entity_id)

    assert len(results) == 2
    assert all(j.entity_id == entity_id for j in results)
