"""Unit tests for shootout-related JobType enum values.

This test verifies that the SHOOTOUT and SHOOTOUT_AUDIO job types
exist in the JobType enum and work correctly with the Job entity.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.domain.entities.job import Job as DomainJob
from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job as ORMJob


class TestShootoutJobTypes:
    """Tests for shootout-related JobType enum values."""

    def test_job_type_shootout_exists(self) -> None:
        """Test that JobType.SHOOTOUT exists with correct value."""
        assert hasattr(JobType, "SHOOTOUT")
        assert JobType.SHOOTOUT.value == "shootout"

    def test_job_type_shootout_audio_exists(self) -> None:
        """Test that JobType.SHOOTOUT_AUDIO exists with correct value."""
        assert hasattr(JobType, "SHOOTOUT_AUDIO")
        assert JobType.SHOOTOUT_AUDIO.value == "shootout_audio"

    def test_job_type_shootout_master_exists(self) -> None:
        """Test that JobType.SHOOTOUT_MASTER exists with correct value."""
        assert hasattr(JobType, "SHOOTOUT_MASTER")
        assert JobType.SHOOTOUT_MASTER.value == "shootout_master"

    def test_existing_job_types_unchanged(self) -> None:
        """Test that existing JobType values are still present."""
        # Verify all existing types from acceptance criteria
        assert JobType.AUDIO_PROCESSING.value == "audio_processing"
        assert JobType.VIDEO_COMPOSITION.value == "video_composition"
        assert JobType.GEAR_SYNC.value == "gear_sync"
        assert JobType.MODEL_DOWNLOAD.value == "model_download"
        assert JobType.IR_DOWNLOAD.value == "ir_download"
        assert JobType.NOTIFICATION.value == "notification"

    def test_all_required_job_types_present(self) -> None:
        """Test that all required JobType values are present."""
        required_values = {
            "audio_processing",
            "video_composition",
            "gear_sync",
            "model_download",
            "ir_download",
            "notification",
            "shootout",
            "shootout_audio",
            "shootout_master",
        }
        actual_values = {member.value for member in JobType}

        assert required_values.issubset(actual_values), (
            f"Missing required JobType values. "
            f"Expected at least {required_values}, got {actual_values}"
        )


class TestDomainJobWithShootoutTypes:
    """Tests for domain Job entity with shootout job types."""

    def test_domain_job_accepts_shootout_type(self) -> None:
        """Test that domain Job entity accepts JobType.SHOOTOUT."""
        entity_id = uuid.uuid4()
        user_id = uuid.uuid4()

        job = DomainJob(
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            entity_id=entity_id,
            status=JobStatus.PENDING,
        )

        assert job.job_type == JobType.SHOOTOUT
        assert job.entity_id == entity_id
        assert job.user_id == user_id

    def test_domain_job_accepts_shootout_audio_type(self) -> None:
        """Test that domain Job entity accepts JobType.SHOOTOUT_AUDIO."""
        entity_id = uuid.uuid4()
        parent_job_id = uuid.uuid4()

        job = DomainJob(
            parent_job_id=parent_job_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            entity_id=entity_id,
            status=JobStatus.PENDING,
        )

        assert job.job_type == JobType.SHOOTOUT_AUDIO
        assert job.entity_id == entity_id
        assert job.parent_job_id == parent_job_id

    def test_shootout_job_state_machine_transitions(self) -> None:
        """Test that shootout jobs work with the Job state machine."""
        job = DomainJob(
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
        )

        # PENDING -> QUEUED
        job.queue(task_id="task-123")
        assert job.status == JobStatus.QUEUED
        assert job.task_id == "task-123"

        # QUEUED -> RUNNING
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.progress == 0

        # RUNNING -> progress update
        job.update_progress(50, "Processing shootout...")
        assert job.progress == 50
        assert job.message == "Processing shootout..."

        # RUNNING -> COMPLETED
        job.complete(result_path="/results/shootout-123.mp4")
        assert job.status == JobStatus.COMPLETED
        assert job.result_path == "/results/shootout-123.mp4"
        assert job.completed_at is not None
        assert job.progress == 100

    def test_shootout_audio_job_state_machine_transitions(self) -> None:
        """Test that shootout_audio jobs work with the Job state machine."""
        parent_id = uuid.uuid4()
        job = DomainJob(
            parent_job_id=parent_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.PENDING,
        )

        # PENDING -> QUEUED -> RUNNING
        job.queue(task_id="audio-task-456")
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.parent_job_id == parent_id

        # RUNNING -> FAILED
        job.fail(error="Audio processing failed")
        assert job.status == JobStatus.FAILED
        assert job.error == "Audio processing failed"
        assert job.completed_at is not None

    def test_shootout_job_cancellation(self) -> None:
        """Test that shootout jobs can be cancelled from valid states."""
        # PENDING -> CANCELLED
        job = DomainJob(
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
        )
        job.cancel()
        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None

        # QUEUED -> CANCELLED
        job2 = DomainJob(
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.PENDING,
        )
        job2.queue(task_id="task-789")
        job2.cancel()
        assert job2.status == JobStatus.CANCELLED


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestORMJobWithShootoutTypes:
    """Tests for ORM Job model with shootout job types (EnumByValue pattern)."""

    async def test_orm_job_stores_shootout_type(self, db_session: AsyncSession) -> None:
        """Test that ORM Job model stores JobType.SHOOTOUT correctly."""
        entity_id = uuid.uuid4()

        job = ORMJob(
            job_type=JobType.SHOOTOUT,
            entity_id=entity_id,
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        await db_session.commit()

        # Refresh to get from database
        await db_session.refresh(job)

        # Verify enum is stored and loaded correctly via EnumByValue
        assert job.job_type == JobType.SHOOTOUT
        assert isinstance(job.job_type, JobType)
        assert job.entity_id == entity_id

    async def test_orm_job_stores_shootout_audio_type(self, db_session: AsyncSession) -> None:
        """Test that ORM Job model stores JobType.SHOOTOUT_AUDIO correctly."""
        parent = ORMJob(
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
        )
        db_session.add(parent)
        await db_session.commit()

        child = ORMJob(
            parent_job_id=parent.id,
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.PENDING,
        )
        db_session.add(child)
        await db_session.commit()

        # Refresh to get from database
        await db_session.refresh(child)

        # Verify enum is stored and loaded correctly via EnumByValue
        assert child.job_type == JobType.SHOOTOUT_AUDIO
        assert isinstance(child.job_type, JobType)
        assert child.parent_job_id == parent.id

    async def test_orm_job_query_by_shootout_type(self, db_session: AsyncSession) -> None:
        """Test that we can query ORM Job by shootout job types."""
        # Create jobs of different types
        shootout_job = ORMJob(
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
        )
        audio_job = ORMJob(
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.QUEUED,
        )
        other_job = ORMJob(
            job_type=JobType.VIDEO_COMPOSITION,
            status=JobStatus.PENDING,
        )
        db_session.add_all([shootout_job, audio_job, other_job])
        await db_session.commit()

        # Query for SHOOTOUT jobs
        stmt = select(ORMJob).where(ORMJob.job_type == JobType.SHOOTOUT)
        result = await db_session.execute(stmt)
        shootout_jobs = result.scalars().all()

        assert len(shootout_jobs) == 1
        assert shootout_jobs[0].job_type == JobType.SHOOTOUT

        # Query for SHOOTOUT_AUDIO jobs
        stmt = select(ORMJob).where(ORMJob.job_type == JobType.SHOOTOUT_AUDIO)
        result = await db_session.execute(stmt)
        audio_jobs = result.scalars().all()

        assert len(audio_jobs) == 1
        assert audio_jobs[0].job_type == JobType.SHOOTOUT_AUDIO

    async def test_orm_job_parent_child_with_shootout_types(self, db_session: AsyncSession) -> None:
        """Test parent/child relationship with shootout job types."""
        # Parent SHOOTOUT job
        parent = ORMJob(
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
            entity_id=uuid.uuid4(),
        )
        db_session.add(parent)
        await db_session.commit()

        # Child SHOOTOUT_AUDIO jobs
        child1 = ORMJob(
            parent_job_id=parent.id,
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.QUEUED,
        )
        child2 = ORMJob(
            parent_job_id=parent.id,
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.PENDING,
        )
        db_session.add_all([child1, child2])
        await db_session.commit()

        # Verify relationships
        assert child1.parent_job_id == parent.id
        assert child2.parent_job_id == parent.id
        assert parent.job_type == JobType.SHOOTOUT
        assert child1.job_type == JobType.SHOOTOUT_AUDIO
        assert child2.job_type == JobType.SHOOTOUT_AUDIO
