"""Unit tests for Shootout Processing Orchestrator Job Handler.

Tests that the SHOOTOUT job handler loads a shootout, creates child
SHOOTOUT_AUDIO jobs for each chain, and manages processing state.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain


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


def _make_fake_get_session(session: AsyncSession):
    """Create a fake get_session context manager that yields the test session."""

    @contextlib.asynccontextmanager
    async def fake_get_session(_url=None):
        yield session

    return fake_get_session


async def _create_shootout_with_chains(
    session: AsyncSession,
    *,
    num_chains: int = 1,
    status: ShootoutStatus = ShootoutStatus.PENDING,
) -> tuple:
    """Create a Shootout with chains and a parent SHOOTOUT Job.

    Returns:
        (parent_job_id, shootout_id, chain_ids)
    """
    user_id = uuid4()

    # DITrack needed for Shootout FK
    di_track = DITrack(
        id=uuid4(),
        user_id=user_id,
        name="Test DI",
        file_path="/uploads/test.wav",
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=48000,
    )
    session.add(di_track)

    shootout_id = uuid4()
    shootout = Shootout(
        id=shootout_id,
        user_id=user_id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=status,
    )
    session.add(shootout)

    # Signal chain needed for ShootoutChain FK
    signal_chain = SignalChain(
        id=uuid4(),
        user_id=user_id,
        name="Test Chain",
    )
    session.add(signal_chain)

    chain_ids = []
    for i in range(num_chains):
        chain_id = uuid4()
        chain = ShootoutChain(
            id=chain_id,
            shootout_id=shootout_id,
            signal_chain_id=signal_chain.id,
            position=i,
            label=f"Chain {chr(65 + i)}",
        )
        session.add(chain)
        chain_ids.append(chain_id)

    parent_job_id = uuid4()
    parent_job = Job(
        id=parent_job_id,
        user_id=user_id,
        job_type=JobType.SHOOTOUT,
        status=JobStatus.PENDING,
        entity_id=shootout_id,
    )
    session.add(parent_job)

    await session.flush()
    return parent_job_id, shootout_id, chain_ids


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

        assert hasattr(handle_shootout_job, "kicker")


class TestShootoutJobHandler:
    """Test handle_shootout_job orchestration logic."""

    async def test_loads_shootout_with_chains(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler loads shootout from database with all chains."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, _, _chain_ids = await _create_shootout_with_chains(db_session, num_chains=2)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        # Verify child jobs were created (proves chains were loaded)
        result = await db_session.execute(select(Job).where(Job.parent_job_id == parent_job_id))
        children = result.scalars().all()
        assert len(children) == 2

    async def test_creates_child_job_per_chain(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler creates one SHOOTOUT_AUDIO child job per chain."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, _, _chain_ids = await _create_shootout_with_chains(db_session, num_chains=3)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        result = await db_session.execute(select(Job).where(Job.parent_job_id == parent_job_id))
        children = result.scalars().all()
        assert len(children) == 3

    async def test_child_jobs_have_correct_type(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Child jobs have job_type set to SHOOTOUT_AUDIO."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, _, _ = await _create_shootout_with_chains(db_session)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        result = await db_session.execute(select(Job).where(Job.parent_job_id == parent_job_id))
        child = result.scalar_one()
        assert child.job_type == JobType.SHOOTOUT_AUDIO

    async def test_child_jobs_have_parent_job_id_set(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Child jobs have parent_job_id set to parent job ID."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, _, _ = await _create_shootout_with_chains(db_session)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        result = await db_session.execute(select(Job).where(Job.parent_job_id == parent_job_id))
        child = result.scalar_one()
        assert child.parent_job_id == parent_job_id

    async def test_child_jobs_have_entity_id_set_to_chain_id(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Child jobs have entity_id set to shootout chain ID."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, _, chain_ids = await _create_shootout_with_chains(db_session)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        result = await db_session.execute(select(Job).where(Job.parent_job_id == parent_job_id))
        child = result.scalar_one()
        assert child.entity_id == chain_ids[0]

    async def test_updates_shootout_status_to_running(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler updates shootout status from PENDING to RUNNING on start."""
        from worker.jobs.shootout import handle_shootout_job

        parent_job_id, shootout_id, _ = await _create_shootout_with_chains(db_session)

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await handle_shootout_job(parent_job_id)

        result = await db_session.execute(select(Shootout).where(Shootout.id == shootout_id))
        shootout = result.scalar_one()
        assert shootout.status == ShootoutStatus.RUNNING

    async def test_updates_parent_progress_when_children_complete(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_update_parent_progress calculates progress from child job completion."""
        from worker.jobs.shootout import _update_parent_progress

        parent_job_id, _shootout_id, chain_ids = await _create_shootout_with_chains(
            db_session, num_chains=2
        )

        # Create child jobs, one completed
        child1 = Job(
            id=uuid4(),
            user_id=(
                await db_session.execute(select(Job.user_id).where(Job.id == parent_job_id))
            ).scalar_one(),
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[0],
            status=JobStatus.COMPLETED,
        )
        child2 = Job(
            id=uuid4(),
            user_id=child1.user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[1],
            status=JobStatus.PENDING,
        )
        db_session.add_all([child1, child2])
        await db_session.flush()

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await _update_parent_progress(parent_job_id, "unused")

        result = await db_session.execute(select(Job).where(Job.id == parent_job_id))
        parent_job = result.scalar_one()
        assert parent_job.progress == 50  # 1 of 2 completed

    async def test_marks_shootout_completed_when_all_children_complete(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_update_parent_progress marks shootout COMPLETED when all children complete."""
        from worker.jobs.shootout import _update_parent_progress

        parent_job_id, shootout_id, chain_ids = await _create_shootout_with_chains(
            db_session, num_chains=2, status=ShootoutStatus.RUNNING
        )

        user_id = (
            await db_session.execute(select(Job.user_id).where(Job.id == parent_job_id))
        ).scalar_one()

        child1 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[0],
            status=JobStatus.COMPLETED,
        )
        child2 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[1],
            status=JobStatus.COMPLETED,
        )
        db_session.add_all([child1, child2])
        await db_session.flush()

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await _update_parent_progress(parent_job_id, "unused")

        result = await db_session.execute(select(Shootout).where(Shootout.id == shootout_id))
        shootout = result.scalar_one()
        assert shootout.status == ShootoutStatus.COMPLETED

    async def test_marks_shootout_failed_when_any_child_fails(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_update_parent_progress marks shootout FAILED if any child fails."""
        from worker.jobs.shootout import _update_parent_progress

        parent_job_id, shootout_id, chain_ids = await _create_shootout_with_chains(
            db_session, num_chains=2, status=ShootoutStatus.RUNNING
        )

        user_id = (
            await db_session.execute(select(Job.user_id).where(Job.id == parent_job_id))
        ).scalar_one()

        child1 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[0],
            status=JobStatus.COMPLETED,
        )
        child2 = Job(
            id=uuid4(),
            user_id=user_id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent_job_id,
            entity_id=chain_ids[1],
            status=JobStatus.FAILED,
            error="Processing failed",
        )
        db_session.add_all([child1, child2])
        await db_session.flush()

        monkeypatch.setattr("worker.jobs.shootout.get_session", _make_fake_get_session(db_session))
        await _update_parent_progress(parent_job_id, "unused")

        result = await db_session.execute(select(Shootout).where(Shootout.id == shootout_id))
        shootout = result.scalar_one()
        assert shootout.status == ShootoutStatus.FAILED


class TestTaskRegistration:
    """Test that handle_shootout_job is registered with TaskIQ broker."""

    def test_task_is_registered_with_broker(self) -> None:
        """handle_shootout_job task is registered with the broker."""
        from worker.main import broker

        task_names = list(broker.get_all_tasks())
        assert any("handle_shootout_job" in name for name in task_names)
