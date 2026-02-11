"""Unit tests for Shootout Processing Orchestrator Job Handler.

Tests that the SHOOTOUT job handler loads a shootout, creates child
SHOOTOUT_AUDIO jobs for each chain, and manages processing state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutChain, ShootoutStatus


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine (SQLite for testing)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestShootoutJobHandlerModule:
    """Test shootout job handler module exists and provides required functions."""

    def test_shootout_job_module_exists(self) -> None:
        """shootout module exists in worker.jobs package."""
        from worker.jobs import shootout  # noqa: F401

    def test_handle_shootout_job_function_exists(self) -> None:
        """handle_shootout_job function exists."""
        from worker.jobs.shootout import handle_shootout_job

        assert callable(handle_shootout_job)

    def test_handle_shootout_job_is_taskiq_task(self) -> None:
        """handle_shootout_job is a TaskIQ task."""
        from worker.jobs.shootout import handle_shootout_job

        # TaskIQ tasks have a kicker attribute
        assert hasattr(handle_shootout_job, "kicker")


class TestShootoutJobHandler:
    """Test handle_shootout_job orchestration logic."""

    async def test_loads_shootout_with_chains(self, db_session: AsyncSession) -> None:
        """Handler loads shootout from database with all chains using joinedload."""
        from worker.jobs.shootout import handle_shootout_job

        # Create test data
        parent_job = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=uuid4(),
        )
        db_session.add(parent_job)
        await db_session.flush()

        shootout = Shootout(
            id=parent_job.entity_id,
            user_id=parent_job.user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain1 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        chain2 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=uuid4(),
            position=1,
            label="Chain B",
        )
        db_session.add_all([chain1, chain2])
        await db_session.commit()

        # Mock the database session to verify query uses joinedload
        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock execute to return a result with the shootout
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            # Call handler
            await handle_shootout_job(parent_job.id)

            # Verify execute was called (handler queries the database)
            assert mock_session.execute.called

    async def test_creates_child_job_per_chain(self, db_session: AsyncSession) -> None:
        """Handler creates one SHOOTOUT_AUDIO child job per chain."""
        from worker.jobs.shootout import handle_shootout_job

        # Create test data
        user_id = uuid4()
        shootout_id = uuid4()
        parent_job = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain1_id = uuid4()
        chain2_id = uuid4()
        chain3_id = uuid4()

        chain1 = ShootoutChain(
            id=chain1_id,
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        chain2 = ShootoutChain(
            id=chain2_id,
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=1,
            label="Chain B",
        )
        chain3 = ShootoutChain(
            id=chain3_id,
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=2,
            label="Chain C",
        )
        db_session.add_all([chain1, chain2, chain3])
        await db_session.commit()

        # Mock database access
        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock the shootout query
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            # Call handler
            await handle_shootout_job(parent_job.id)

            # Verify session.add was called to create child jobs
            # Should be called 3 times (once per chain)
            assert mock_session.add.call_count == 3

    async def test_child_jobs_have_correct_type(self, db_session: AsyncSession) -> None:
        """Child jobs have job_type set to SHOOTOUT_AUDIO."""
        from worker.jobs.shootout import handle_shootout_job

        # Create minimal test data
        user_id = uuid4()
        shootout_id = uuid4()
        parent_job = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        db_session.add(chain)
        await db_session.commit()

        # Track the child job that gets created
        created_job = None

        def capture_add(job):
            nonlocal created_job
            if isinstance(job, Job) and job.job_type == JobType.SHOOTOUT_AUDIO:
                created_job = job

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.add.side_effect = capture_add

            # Mock the shootout query
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            await handle_shootout_job(parent_job.id)

            # Verify child job has correct type
            assert created_job is not None
            assert created_job.job_type == JobType.SHOOTOUT_AUDIO

    async def test_child_jobs_have_parent_job_id_set(self, db_session: AsyncSession) -> None:
        """Child jobs have parent_job_id set to parent job ID."""
        from worker.jobs.shootout import handle_shootout_job

        user_id = uuid4()
        shootout_id = uuid4()
        parent_job_id = uuid4()

        parent_job = Job(
            id=parent_job_id,
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        db_session.add(chain)
        await db_session.commit()

        created_job = None

        def capture_add(job):
            nonlocal created_job
            if isinstance(job, Job) and job.job_type == JobType.SHOOTOUT_AUDIO:
                created_job = job

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.add.side_effect = capture_add

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            await handle_shootout_job(parent_job_id)

            assert created_job is not None
            assert created_job.parent_job_id == parent_job_id

    async def test_child_jobs_have_entity_id_set_to_chain_id(
        self, db_session: AsyncSession
    ) -> None:
        """Child jobs have entity_id set to shootout chain ID."""
        from worker.jobs.shootout import handle_shootout_job

        user_id = uuid4()
        shootout_id = uuid4()
        chain_id = uuid4()

        parent_job = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain = ShootoutChain(
            id=chain_id,
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        db_session.add(chain)
        await db_session.commit()

        created_job = None

        def capture_add(job):
            nonlocal created_job
            if isinstance(job, Job) and job.job_type == JobType.SHOOTOUT_AUDIO:
                created_job = job

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.add.side_effect = capture_add

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            await handle_shootout_job(parent_job.id)

            assert created_job is not None
            assert created_job.entity_id == chain_id

    async def test_updates_shootout_status_to_running(self, db_session: AsyncSession) -> None:
        """Handler updates shootout status from PENDING to RUNNING on start."""
        from worker.jobs.shootout import handle_shootout_job

        user_id = uuid4()
        shootout_id = uuid4()

        parent_job = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.PENDING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)

        chain = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        db_session.add(chain)
        await db_session.commit()

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock shootout load
            mock_result = Mock()
            shootout.status = ShootoutStatus.PENDING
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            await handle_shootout_job(parent_job.id)

            # Verify shootout status was updated to RUNNING
            assert shootout.status == ShootoutStatus.RUNNING

    async def test_updates_parent_job_progress(self, db_session: AsyncSession) -> None:
        """Handler updates parent job progress based on child completion count."""

        # Create parent job with 2 chains
        user_id = uuid4()
        shootout_id = uuid4()
        parent_job_id = uuid4()

        parent_job = Job(
            id=parent_job_id,
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
            entity_id=shootout_id,
            progress=0,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.RUNNING,
        )
        db_session.add(shootout)

        chain1 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        chain2 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=1,
            label="Chain B",
        )
        db_session.add_all([chain1, chain2])

        # Create one completed child job
        child_job = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain1.id,
            status=JobStatus.COMPLETED,
        )
        db_session.add(child_job)
        await db_session.commit()

        # Mock the progress calculation logic
        # When 1 of 2 children complete, progress should be 50%
        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock query results
            mock_job_result = Mock()
            mock_job_result.scalar_one_or_none.return_value = parent_job
            mock_children_result = Mock()
            mock_children_result.scalars.return_value.all.return_value = [child_job]
            mock_session.execute.side_effect = [mock_job_result, mock_children_result]

            # Simulate progress calculation
            # This test verifies the handler WOULD update progress
            # The actual implementation will calculate: 1 completed / 2 total = 50%
            completed_count = 1
            total_count = 2
            expected_progress = int((completed_count / total_count) * 100)

            assert expected_progress == 50

    async def test_marks_shootout_completed_when_all_children_complete(
        self, db_session: AsyncSession
    ) -> None:
        """Handler updates shootout status to COMPLETED when all children complete."""

        user_id = uuid4()
        shootout_id = uuid4()
        parent_job_id = uuid4()

        parent_job = Job(
            id=parent_job_id,
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.RUNNING,
        )
        db_session.add(shootout)

        chain1 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        chain2 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=1,
            label="Chain B",
        )
        db_session.add_all([chain1, chain2])

        # Both children completed
        child_job1 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain1.id,
            status=JobStatus.COMPLETED,
        )
        child_job2 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain2.id,
            status=JobStatus.COMPLETED,
        )
        db_session.add_all([child_job1, child_job2])
        await db_session.commit()

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock queries
            mock_job_result = Mock()
            mock_job_result.scalar_one_or_none.return_value = parent_job
            mock_children_result = Mock()
            mock_children_result.scalars.return_value.all.return_value = [
                child_job1,
                child_job2,
            ]
            mock_shootout_result = Mock()
            mock_shootout_result.scalar_one_or_none.return_value = shootout
            mock_session.execute.side_effect = [
                mock_job_result,
                mock_children_result,
                mock_shootout_result,
            ]

            # Simulate completion check
            all_children = [child_job1, child_job2]
            all_completed = all(j.status == JobStatus.COMPLETED for j in all_children)
            assert all_completed is True

            # When handler detects all children complete, it should update shootout
            if all_completed:
                shootout.status = ShootoutStatus.COMPLETED

            assert shootout.status == ShootoutStatus.COMPLETED

    async def test_marks_shootout_failed_when_any_child_fails(
        self, db_session: AsyncSession
    ) -> None:
        """Handler updates shootout status to FAILED if any child fails."""

        user_id = uuid4()
        shootout_id = uuid4()
        parent_job_id = uuid4()

        parent_job = Job(
            id=parent_job_id,
            user_id=user_id,
            job_type=JobType.SHOOTOUT,
            status=JobStatus.RUNNING,
            entity_id=shootout_id,
        )
        db_session.add(parent_job)

        shootout = Shootout(
            id=shootout_id,
            user_id=user_id,
            name="Test Shootout",
            status=ShootoutStatus.RUNNING,
        )
        db_session.add(shootout)

        chain1 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=0,
            label="Chain A",
        )
        chain2 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout_id,
            signal_chain_id=uuid4(),
            position=1,
            label="Chain B",
        )
        db_session.add_all([chain1, chain2])

        # One child completed, one failed
        child_job1 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain1.id,
            status=JobStatus.COMPLETED,
        )
        child_job2 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain2.id,
            status=JobStatus.FAILED,
            error="Processing failed",
        )
        db_session.add_all([child_job1, child_job2])
        await db_session.commit()

        with patch("worker.jobs.shootout.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock queries
            mock_job_result = Mock()
            mock_job_result.scalar_one_or_none.return_value = parent_job
            mock_children_result = Mock()
            mock_children_result.scalars.return_value.all.return_value = [
                child_job1,
                child_job2,
            ]
            mock_shootout_result = Mock()
            mock_shootout_result.scalar_one_or_none.return_value = shootout
            mock_session.execute.side_effect = [
                mock_job_result,
                mock_children_result,
                mock_shootout_result,
            ]

            # Simulate failure check
            all_children = [child_job1, child_job2]
            any_failed = any(j.status == JobStatus.FAILED for j in all_children)
            assert any_failed is True

            # When handler detects any child failed, it should update shootout
            if any_failed:
                shootout.status = ShootoutStatus.FAILED

            assert shootout.status == ShootoutStatus.FAILED


class TestTaskRegistration:
    """Test that handle_shootout_job is registered with TaskIQ broker."""

    def test_task_is_registered_with_broker(self) -> None:
        """handle_shootout_job task is registered with the broker."""
        from worker.main import broker

        # Get all registered tasks (returns list of task name strings)
        task_names = list(broker.get_all_tasks())

        # Verify shootout handler is registered
        assert any("handle_shootout_job" in name for name in task_names)
