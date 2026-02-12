"""Integration tests for scheduler sync dispatch (T119).

Tests that:
- ensure_source_sync_running dispatches handle_source_sync when no Redis lock
- ensure_source_sync_running skips dispatch when Redis lock exists
- ensure_source_sync_running skips dispatch when T3K_SYNC_ENABLED=false
- handle_source_sync job creates T3K session and invokes catalog sync
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import Base as T3KBase
from webapp.adapters.persistence.models.base import Base as CoreBase
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine


# ---------------------------------------------------------------------------
# FakeRedis (same pattern as tests/unit/worker/test_admin_api_extensions.py)
# ---------------------------------------------------------------------------


class FakeRedis:
    """Fake Redis client for integration tests — not a mock."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._data else 0

    async def set(self, key: str, value: str, **kwargs) -> None:
        """Set key."""
        self._data[key] = value

    async def delete(self, key: str) -> int:
        """Delete key."""
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def aclose(self) -> None:
        """Close connection (no-op for fake)."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def scheduler_env(monkeypatch) -> None:
    """Set environment variables needed for scheduler imports."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db/gts_core")
    monkeypatch.setenv("T3K_DATABASE_URL", "postgresql+asyncpg://user:pass@db/gts_t3k_source")


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite engine with both Core and T3K tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(CoreBase.metadata.create_all)
        await conn.run_sync(T3KBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for test data."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def fake_redis() -> FakeRedis:
    """FakeRedis with no keys set (no lock)."""
    return FakeRedis()


@pytest.fixture
def fake_redis_with_lock() -> FakeRedis:
    """FakeRedis with sync lock already set."""
    redis = FakeRedis()
    redis._data["t3k:sync:lock"] = "1"
    return redis


@pytest.fixture
async def register_engines(db_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Register test engine so get_t3k_session and get_core_session resolve."""
    from worker.db import _engine_cache, register_engine

    register_engine("postgresql+asyncpg://user:pass@db/gts_core", db_engine)
    register_engine("postgresql+asyncpg://user:pass@db/gts_t3k_source", db_engine)
    yield
    _engine_cache.clear()


# ---------------------------------------------------------------------------
# ensure_source_sync_running — dispatch tests
# ---------------------------------------------------------------------------


class TestEnsureSourceSyncRunningDispatches:
    """ensure_source_sync_running must dispatch handle_source_sync when appropriate."""

    async def test_dispatches_when_no_lock_and_sync_enabled(
        self,
        fake_redis: FakeRedis,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        register_engines: None,
        monkeypatch,
    ) -> None:
        """With no Redis lock and T3K_SYNC_ENABLED=true, dispatches handle_source_sync.

        The function must:
        1. Check Redis for t3k:sync:lock — absent
        2. Check T3K_SYNC_ENABLED env var — true
        3. Create a SOURCE_SYNC Job record in the database
        4. Await handle_source_sync.kiq(job_id)
        """
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        from scheduler.schedules.jobs import ensure_source_sync_running

        # Inject fake Redis so we don't need a real Redis connection
        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )

        # Track whether dispatch was called
        dispatched_job_ids: list = []

        # Create a fake kiq that records the dispatch
        async def tracking_kiq(job_id):
            dispatched_job_ids.append(job_id)

            class FakeResult:
                task_id = "test-task-id"

            return FakeResult()

        from scheduler.schedules.jobs import handle_source_sync

        monkeypatch.setattr(handle_source_sync, "kiq", tracking_kiq)

        await ensure_source_sync_running()

        # Verify dispatch happened
        assert (
            len(dispatched_job_ids) == 1
        ), "ensure_source_sync_running must dispatch exactly one job"
        # The dispatched job_id should be a valid UUID
        assert dispatched_job_ids[0] is not None

    async def test_does_not_dispatch_when_lock_exists(
        self,
        fake_redis_with_lock: FakeRedis,
        monkeypatch,
    ) -> None:
        """With existing Redis lock, does NOT dispatch a duplicate sync job.

        If t3k:sync:lock exists in Redis, the scheduler must skip dispatch
        because a sync is already running.
        """
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis_with_lock,
        )

        dispatched: list = []

        async def tracking_kiq(job_id):
            dispatched.append(job_id)

            class FakeResult:
                task_id = "test-task-id"

            return FakeResult()

        from scheduler.schedules.jobs import handle_source_sync

        monkeypatch.setattr(handle_source_sync, "kiq", tracking_kiq)

        await ensure_source_sync_running()

        assert (
            len(dispatched) == 0
        ), "ensure_source_sync_running must NOT dispatch when Redis lock exists"

    async def test_does_not_dispatch_when_sync_disabled(
        self,
        fake_redis: FakeRedis,
        monkeypatch,
    ) -> None:
        """With T3K_SYNC_ENABLED=false, does NOT dispatch even without lock.

        The scheduler respects the config flag to disable sync entirely.
        """
        monkeypatch.setenv("T3K_SYNC_ENABLED", "false")

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )

        dispatched: list = []

        async def tracking_kiq(job_id):
            dispatched.append(job_id)

            class FakeResult:
                task_id = "test-task-id"

            return FakeResult()

        from scheduler.schedules.jobs import handle_source_sync

        monkeypatch.setattr(handle_source_sync, "kiq", tracking_kiq)

        await ensure_source_sync_running()

        assert (
            len(dispatched) == 0
        ), "ensure_source_sync_running must NOT dispatch when T3K_SYNC_ENABLED=false"

    async def test_dispatch_creates_job_record_in_database(
        self,
        fake_redis: FakeRedis,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        register_engines: None,
        monkeypatch,
    ) -> None:
        """Dispatching sync must create a SOURCE_SYNC Job record in the DB.

        The scheduler should create a Job record BEFORE dispatching to TaskIQ
        so that the job is tracked in the database regardless of broker state.
        """
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )

        dispatched_job_ids: list = []

        async def tracking_kiq(job_id):
            dispatched_job_ids.append(job_id)

            class FakeResult:
                task_id = "test-task-id"

            return FakeResult()

        from scheduler.schedules.jobs import handle_source_sync

        monkeypatch.setattr(handle_source_sync, "kiq", tracking_kiq)

        await ensure_source_sync_running()

        # Verify Job record was created
        from core.domain.value_objects.job_status import JobType

        result = await db_session.execute(select(Job).where(Job.job_type == JobType.SOURCE_SYNC))
        jobs = result.scalars().all()
        assert len(jobs) >= 1, "ensure_source_sync_running must create a SOURCE_SYNC Job record"

        # The dispatched job_id should match the created job
        created_job = jobs[0]
        assert dispatched_job_ids[0] == created_job.id

    async def test_dispatch_awaits_kiq_coroutine(
        self,
        fake_redis: FakeRedis,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        register_engines: None,
        monkeypatch,
    ) -> None:
        """ensure_source_sync_running must await the kiq() coroutine.

        If kiq() is not awaited, the task is never actually dispatched.
        """
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )

        kiq_was_awaited = []

        async def tracking_kiq(job_id):
            """Async function — must be awaited to execute."""
            kiq_was_awaited.append(True)

            class FakeResult:
                task_id = "test-task-id"

            return FakeResult()

        from scheduler.schedules.jobs import handle_source_sync

        monkeypatch.setattr(handle_source_sync, "kiq", tracking_kiq)

        await ensure_source_sync_running()

        # If kiq() was not awaited, the async function body never runs
        assert (
            len(kiq_was_awaited) == 1
        ), "kiq() must be awaited — currently the coroutine is created but never executed"


# ---------------------------------------------------------------------------
# ensure_source_sync_running — schedule configuration
# ---------------------------------------------------------------------------


class TestEnsureSourceSyncScheduleConfig:
    """ensure_source_sync_running schedule metadata."""

    def test_has_schedule_label(self) -> None:
        """ensure_source_sync_running has a TaskIQ schedule label."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        assert hasattr(ensure_source_sync_running, "labels")
        assert "schedule" in ensure_source_sync_running.labels

    def test_schedule_interval_is_5_minutes(self) -> None:
        """ensure_source_sync_running runs every 5 minutes (300 seconds)."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        schedule = ensure_source_sync_running.labels["schedule"][0]
        assert schedule.seconds == 300


# ---------------------------------------------------------------------------
# handle_source_sync — job wiring
# ---------------------------------------------------------------------------


class TestHandleSourceSyncJob:
    """handle_source_sync job must create T3K session and run catalog sync."""

    def test_handle_source_sync_is_broker_task(self) -> None:
        """handle_source_sync is registered as a TaskIQ broker task."""
        from worker.jobs.source_sync import handle_source_sync

        # TaskIQ broker tasks have task_name attribute
        assert hasattr(handle_source_sync, "task_name")

    def test_handle_source_sync_accepts_job_id(self) -> None:
        """handle_source_sync accepts a job_id: UUID parameter."""
        import inspect

        from worker.jobs.source_sync import handle_source_sync

        # Get the original function signature
        sig = inspect.signature(handle_source_sync.__wrapped__)
        params = list(sig.parameters.keys())
        assert "job_id" in params
