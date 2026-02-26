"""Regression test: validates ORM -> Repository -> Database stack.

Run with: just test-regression
Pass = Stack works | Fail = Something fundamental is broken
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from gts.domain.entities.job import Job as JobEntity
from gts.domain.entities.user import User as UserEntity
from gts.domain.entities.user import UserIdentity
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.job_repository import SQLAlchemyJobRepository
from webapp.adapters.persistence.repositories.user_repository import SQLAlchemyUserRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestStackConnectivity:
    """Verify ORM -> Repository -> Database stack is connected."""

    def test_orm_models_import(self) -> None:
        """ORM models can be imported."""
        assert Base is not None
        assert User is not None
        assert User.__tablename__ == "core_users"

    def test_domain_entities_import(self) -> None:
        """Domain entities can be imported."""
        assert UserEntity is not None
        assert UserIdentity is not None

    @pytest.mark.asyncio
    async def test_session_created(self, db_session: AsyncSession) -> None:
        """Database session can be created."""
        assert db_session is not None


class TestUserRoundTrip:
    """Verify User entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Create user via repository, retrieve it - validates full stack."""
        identity = UserIdentity(provider="t3k", external_id="test-001", username="test_user")
        user = UserEntity.create_with_identity(identity=identity, email="test@gts.dev")
        original_id = user.id

        repo = SQLAlchemyUserRepository(db_session)
        await repo.save(user)
        await db_session.commit()

        retrieved = await repo.get_by_id(original_id)

        assert retrieved is not None, "User should be retrievable"
        assert retrieved.id == original_id
        assert retrieved.username == "test_user"
        assert retrieved.email == "test@gts.dev"
        assert len(retrieved.identities) == 1
        assert retrieved.identities[0].provider == "t3k"

    @pytest.mark.asyncio
    async def test_query_by_email(self, db_session: AsyncSession) -> None:
        """User can be queried by email."""
        identity = UserIdentity(provider="t3k", external_id="email-001", username="u")
        user = UserEntity.create_with_identity(identity=identity, email="q@test.gts")

        repo = SQLAlchemyUserRepository(db_session)
        await repo.save(user)
        await db_session.commit()

        retrieved = await repo.get_by_email("q@test.gts")
        assert retrieved is not None
        assert retrieved.email == "q@test.gts"

    @pytest.mark.asyncio
    async def test_query_by_identity(self, db_session: AsyncSession) -> None:
        """User can be queried by external identity."""
        identity = UserIdentity(provider="t3k", external_id="id-001", username="u")
        user = UserEntity.create_with_identity(identity=identity)

        repo = SQLAlchemyUserRepository(db_session)
        await repo.save(user)
        await db_session.commit()

        retrieved = await repo.get_by_identity("t3k", "id-001")
        assert retrieved is not None
        assert retrieved.identities[0].external_id == "id-001"


class TestJobRoundTrip:
    """Verify Job entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Create job via repository, retrieve it - validates Job stack."""
        job = JobEntity(job_type=JobType.AUDIO_PROCESSING, message="Test job")
        original_id = job.id

        repo = SQLAlchemyJobRepository(db_session)
        await repo.save(job)
        await db_session.commit()

        retrieved = await repo.get_by_id(original_id)

        assert retrieved is not None, "Job should be retrievable"
        assert retrieved.id == original_id
        assert retrieved.job_type == JobType.AUDIO_PROCESSING
        assert retrieved.status == JobStatus.PENDING
        assert retrieved.message == "Test job"

    @pytest.mark.asyncio
    async def test_job_state_transitions(self, db_session: AsyncSession) -> None:
        """Job state machine works correctly."""
        job = JobEntity(job_type=JobType.AUDIO_PROCESSING)

        # Queue the job
        job.queue(task_id="test-task-123")
        assert job.status == JobStatus.QUEUED

        # Start the job
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

        # Update progress
        job.update_progress(50, "Halfway done")
        assert job.progress == 50
        assert job.message == "Halfway done"

        # Complete the job
        job.complete(result_path="/results/test.wav")
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.result_path == "/results/test.wav"

        # Save and retrieve to verify persistence
        repo = SQLAlchemyJobRepository(db_session)
        await repo.save(job)
        await db_session.commit()

        retrieved = await repo.get_by_id(job.id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.COMPLETED
        assert retrieved.result_path == "/results/test.wav"
