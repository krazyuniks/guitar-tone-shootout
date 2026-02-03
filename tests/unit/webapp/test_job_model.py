"""Unit tests for Job and Audit ORM models."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import AuditLog, Job
from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.mark.asyncio
async def test_job_creation(db_session: AsyncSession) -> None:
    """Test creating a Job model with basic fields."""
    # Create a user first
    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    # Create a job
    job = Job(
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        entity_id=uuid.uuid4(),
        status=JobStatus.PENDING,
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    # Verify fields
    assert job.id is not None
    assert job.user_id == user.id
    assert job.job_type == JobType.AUDIO_PROCESSING
    assert job.status == JobStatus.PENDING
    assert job.progress == 0
    assert job.created_at is not None
    assert job.updated_at is not None


@pytest.mark.asyncio
async def test_job_parent_child_relationship(db_session: AsyncSession) -> None:
    """Test parent/child job relationships."""
    # Create parent job
    parent = Job(
        job_type=JobType.VIDEO_COMPOSITION,
        status=JobStatus.RUNNING,
    )
    db_session.add(parent)
    await db_session.commit()

    # Create child jobs
    child1 = Job(
        parent_job_id=parent.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.QUEUED,
    )
    child2 = Job(
        parent_job_id=parent.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
    )
    db_session.add_all([child1, child2])
    await db_session.commit()

    # Verify relationships
    assert child1.parent_job_id == parent.id
    assert child2.parent_job_id == parent.id


@pytest.mark.asyncio
async def test_job_all_fields(db_session: AsyncSession) -> None:
    """Test Job model with all optional fields populated."""
    user = User(username="testuser")
    db_session.add(user)
    await db_session.commit()

    job = Job(
        user_id=user.id,
        job_type=JobType.GEAR_SYNC,
        entity_id=uuid.uuid4(),
        status=JobStatus.RUNNING,
        progress=50,
        message="Processing gear sync...",
        started_at=datetime.now(UTC),
        last_heartbeat=datetime.now(UTC),
        attempt=1,
        max_attempts=3,
        task_id="task-123",
        result_path="/results/output.json",
    )
    db_session.add(job)
    await db_session.commit()

    # Verify all fields
    assert job.progress == 50
    assert job.message == "Processing gear sync..."
    assert job.started_at is not None
    assert job.last_heartbeat is not None
    assert job.attempt == 1
    assert job.max_attempts == 3
    assert job.task_id == "task-123"
    assert job.result_path == "/results/output.json"


@pytest.mark.asyncio
async def test_job_status_enum_storage(db_session: AsyncSession) -> None:
    """Test that JobStatus enum is stored by value."""
    job = Job(
        job_type=JobType.MODEL_DOWNLOAD,
        status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()

    # Refresh to get from database
    await db_session.refresh(job)

    # Verify enum is stored and loaded correctly
    assert job.status == JobStatus.COMPLETED
    assert isinstance(job.status, JobStatus)


@pytest.mark.asyncio
async def test_job_indexes(db_session: AsyncSession) -> None:
    """Test that Job indexes are created correctly."""
    # This is mainly verified by the model definition and schema creation
    # Just verify we can create and query by indexed fields
    user = User(username="testuser")
    db_session.add(user)
    await db_session.commit()

    job1 = Job(user_id=user.id, job_type=JobType.AUDIO_PROCESSING, status=JobStatus.PENDING)
    job2 = Job(user_id=user.id, job_type=JobType.GEAR_SYNC, status=JobStatus.RUNNING)
    db_session.add_all([job1, job2])
    await db_session.commit()

    # Verify we can query by indexed fields (no errors)
    assert job1.user_id == user.id
    assert job1.status == JobStatus.PENDING
    assert job2.status == JobStatus.RUNNING


@pytest.mark.asyncio
async def test_audit_log_creation(db_session: AsyncSession) -> None:
    """Test creating an AuditLog model."""
    user = User(username="testuser")
    db_session.add(user)
    await db_session.commit()

    # Create audit log entry
    audit = AuditLog(
        user_id=user.id,
        action="CREATE",
        resource_type="SHOOTOUT",
        resource_id=uuid.uuid4(),
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
    )
    db_session.add(audit)
    await db_session.commit()

    # Verify fields
    assert audit.id is not None
    assert audit.timestamp is not None
    assert audit.user_id == user.id
    assert audit.action == "CREATE"
    assert audit.resource_type == "SHOOTOUT"
    assert audit.ip_address == "192.168.1.1"
    assert audit.user_agent == "Mozilla/5.0"


@pytest.mark.asyncio
async def test_audit_log_with_changes(db_session: AsyncSession) -> None:
    """Test AuditLog with changes field."""
    audit = AuditLog(
        action="UPDATE",
        resource_type="JOB",
        resource_id=uuid.uuid4(),
        changes={"before": {"status": "pending"}, "after": {"status": "running"}},
        extra_data={"retry_count": 1},
    )
    db_session.add(audit)
    await db_session.commit()

    # Verify JSON fields
    assert audit.changes is not None
    assert audit.changes["before"]["status"] == "pending"
    assert audit.changes["after"]["status"] == "running"
    assert audit.extra_data is not None
    assert audit.extra_data["retry_count"] == 1
