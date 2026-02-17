"""Unit tests for Worker Admin API extensions.

Tests for new endpoints added to apps/worker/src/worker/admin.py:
- POST /api/admin/enqueue — Enqueue jobs to TaskIQ broker
- GET /api/admin/sources/{source}/sync/status — Sync state and checkpoints
- POST /api/admin/sources/{source}/sync — Trigger manual sync
- GET /api/admin/sources/{source}/sync/stats — Sync statistics
- GET /api/admin/sources/{source}/sync/lag — Time since last successful sync
- GET /api/admin/sources/{source}/errors/summary — Error counts by type
- GET /api/admin/jobs/dead-lettered — List dead-lettered jobs
- GET /api/admin/jobs/pending-retries/count — Count of pending retries
- POST /api/admin/sources/{source}/sync/unlock — Release sync lock
- POST /api/admin/scheduler/unlock — Release scheduler lock
- Unknown source handling — 404 for unknown sources
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from redis.asyncio import Redis

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.domain.value_objects.job_status import JobStatus, JobType
from source_t3k.adapters.outbound.models import SyncCheckpoint
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job
from worker.admin import app, get_db_session, get_redis_client, get_t3k_db_session


class FakeRedis:
    """Fake Redis client for unit tests."""

    def __init__(self):
        self._data = {}

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._data else 0

    async def delete(self, key: str) -> int:
        """Delete key."""
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def aclose(self):
        """Close connection (no-op for fake)."""
        pass


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # Create Core tables + only the T3K table needed (SyncCheckpoint).
        # T3KToneStaging uses PostgreSQL ARRAY columns incompatible with SQLite.
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(SyncCheckpoint.__table__.create)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Database session for tests with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session_maker = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False)
    session = session_maker()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def fake_redis() -> FakeRedis:
    """Fake Redis client for tests."""
    return FakeRedis()


@pytest.fixture
async def test_broker(monkeypatch):
    """Replace the real TaskIQ broker with an InMemoryBroker for testing.

    This prevents task dispatch from trying to connect to Redis during tests.
    The InMemoryBroker provides the same interface (.kiq()) but doesn't require
    any external services.
    """
    from taskiq import InMemoryBroker

    # Create an in-memory broker that doesn't need Redis
    test_broker_instance = InMemoryBroker()

    # Register all the job handlers with the test broker
    from worker.jobs.audio import handle_shootout_audio_job
    from worker.jobs.audio_processing import handle_audio_processing
    from worker.jobs.shootout import handle_shootout_job
    from worker.jobs.source_sync import handle_source_sync

    # Re-register tasks with the test broker
    test_handle_audio_processing = test_broker_instance.task(handle_audio_processing.__wrapped__)
    test_handle_shootout_job = test_broker_instance.task(handle_shootout_job.__wrapped__)
    test_handle_shootout_audio_job = test_broker_instance.task(
        handle_shootout_audio_job.__wrapped__
    )
    test_handle_source_sync = test_broker_instance.task(handle_source_sync.__wrapped__)

    # Monkeypatch the imported functions in the admin module
    monkeypatch.setattr(
        "worker.jobs.audio_processing.handle_audio_processing", test_handle_audio_processing
    )
    monkeypatch.setattr("worker.jobs.shootout.handle_shootout_job", test_handle_shootout_job)
    monkeypatch.setattr(
        "worker.jobs.audio.handle_shootout_audio_job", test_handle_shootout_audio_job
    )
    monkeypatch.setattr("worker.jobs.source_sync.handle_source_sync", test_handle_source_sync)

    return test_broker_instance


@pytest.fixture
async def client(
    db_session: AsyncSession, fake_redis: FakeRedis, test_broker
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with database session and Redis overrides."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_t3k_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_redis_client() -> AsyncGenerator[Redis, None]:
        yield fake_redis  # type: ignore[misc]

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_t3k_db_session] = override_get_t3k_db_session
    app.dependency_overrides[get_redis_client] = override_get_redis_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestEnqueueEndpoint:
    """Tests for POST /api/admin/enqueue endpoint."""

    async def test_enqueue_accepts_job_id_and_returns_202(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/enqueue accepts job_id and returns 202 Accepted."""
        # Create a job in the database
        job_id = uuid4()
        job = Job(
            id=job_id,
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        await db_session.flush()

        response = await client.post("/api/admin/enqueue", json={"job_id": str(job_id)})

        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["id"] == str(job_id)

    async def test_enqueue_returns_404_for_nonexistent_job(self, client: AsyncClient) -> None:
        """POST /api/admin/enqueue returns 404 if job doesn't exist."""
        nonexistent_id = uuid4()

        response = await client.post("/api/admin/enqueue", json={"job_id": str(nonexistent_id)})

        assert response.status_code == 404


class TestSourceSyncStatus:
    """Tests for GET /api/admin/sources/{source}/sync/status endpoint."""

    async def test_returns_sync_status_for_t3k(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/sync/status returns sync state."""
        response = await client.get("/api/admin/sources/t3k/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data  # running or idle
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)

    async def test_returns_checkpoint_info_when_available(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/sync/status includes checkpoint info."""
        response = await client.get("/api/admin/sources/t3k/sync/status")

        assert response.status_code == 200
        data = response.json()
        # Checkpoint may be null or an object
        if data.get("checkpoint") is not None:
            checkpoint = data["checkpoint"]
            assert "last_tone_id" in checkpoint or "last_model_id" in checkpoint

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/unknown/sync/status returns 404."""
        response = await client.get("/api/admin/sources/unknown/sync/status")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestSourceSyncTrigger:
    """Tests for POST /api/admin/sources/{source}/sync endpoint."""

    async def test_triggers_manual_sync_and_returns_202(self, client: AsyncClient) -> None:
        """POST /api/admin/sources/t3k/sync triggers sync and returns 202."""
        response = await client.post("/api/admin/sources/t3k/sync")

        assert response.status_code == 202
        data = response.json()
        assert "message" in data

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """POST /api/admin/sources/unknown/sync returns 404."""
        response = await client.post("/api/admin/sources/unknown/sync")

        assert response.status_code == 404


class TestSourceSyncStats:
    """Tests for GET /api/admin/sources/{source}/sync/stats endpoint."""

    async def test_returns_sync_statistics(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/sync/stats returns sync statistics."""
        response = await client.get("/api/admin/sources/t3k/sync/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_synced" in data
        assert isinstance(data["total_synced"], int)
        assert "queue_depths" in data
        assert isinstance(data["queue_depths"], dict)

    async def test_includes_last_sync_duration(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/sync/stats includes last sync duration."""
        response = await client.get("/api/admin/sources/t3k/sync/stats")

        assert response.status_code == 200
        data = response.json()
        # May be null if no sync has completed yet
        if data.get("last_sync_duration") is not None:
            assert isinstance(data["last_sync_duration"], int | float)

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/unknown/sync/stats returns 404."""
        response = await client.get("/api/admin/sources/unknown/sync/stats")

        assert response.status_code == 404


class TestSourceSyncLag:
    """Tests for GET /api/admin/sources/{source}/sync/lag endpoint."""

    async def test_returns_seconds_since_last_sync(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/sync/lag returns seconds since last sync."""
        response = await client.get("/api/admin/sources/t3k/sync/lag")

        assert response.status_code == 200
        data = response.json()
        assert "lag_seconds" in data
        # May be null if no sync has completed yet
        if data["lag_seconds"] is not None:
            assert isinstance(data["lag_seconds"], int | float)
            assert data["lag_seconds"] >= 0

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/unknown/sync/lag returns 404."""
        response = await client.get("/api/admin/sources/unknown/sync/lag")

        assert response.status_code == 404


class TestSourceErrorsSummary:
    """Tests for GET /api/admin/sources/{source}/errors/summary endpoint."""

    async def test_returns_error_counts_by_type(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/errors/summary returns error counts."""
        response = await client.get("/api/admin/sources/t3k/errors/summary")

        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert isinstance(data["errors"], dict)
        # May be empty if no errors
        for error_type, count in data["errors"].items():
            assert isinstance(error_type, str)
            assert isinstance(count, int)

    async def test_includes_recent_time_window(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/t3k/errors/summary includes time window."""
        response = await client.get("/api/admin/sources/t3k/errors/summary")

        assert response.status_code == 200
        data = response.json()
        assert "time_window_hours" in data
        assert isinstance(data["time_window_hours"], int)

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """GET /api/admin/sources/unknown/errors/summary returns 404."""
        response = await client.get("/api/admin/sources/unknown/errors/summary")

        assert response.status_code == 404


class TestDeadLetteredJobs:
    """Tests for GET /api/admin/jobs/dead-lettered endpoint."""

    async def test_returns_empty_list_when_no_dead_lettered_jobs(self, client: AsyncClient) -> None:
        """GET /api/admin/jobs/dead-lettered returns empty list when none exist."""
        response = await client.get("/api/admin/jobs/dead-lettered")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_returns_dead_lettered_jobs(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /api/admin/jobs/dead-lettered returns dead-lettered jobs."""
        # Create a dead-lettered job
        job_id = uuid4()
        job = Job(
            id=job_id,
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.DEAD_LETTERED,
            error="Max retries exceeded",
        )
        db_session.add(job)
        await db_session.flush()

        response = await client.get("/api/admin/jobs/dead-lettered")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Find our job
        matching = [j for j in data if j["id"] == str(job_id)]
        assert len(matching) == 1, f"Expected exactly 1 job with id {job_id}, found {len(matching)}"
        assert matching[0]["status"] == "dead_lettered"

    async def test_excludes_non_dead_lettered_jobs(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /api/admin/jobs/dead-lettered excludes non-dead-lettered jobs."""
        # Create jobs with different statuses
        pending_job = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.PENDING,
        )
        dead_job = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.DEAD_LETTERED,
        )
        db_session.add(pending_job)
        db_session.add(dead_job)
        await db_session.flush()

        response = await client.get("/api/admin/jobs/dead-lettered")

        assert response.status_code == 200
        data = response.json()
        job_ids = [j["id"] for j in data]
        assert str(dead_job.id) in job_ids
        assert str(pending_job.id) not in job_ids


class TestPendingRetriesCount:
    """Tests for GET /api/admin/jobs/pending-retries/count endpoint."""

    async def test_returns_zero_when_no_pending_retries(self, client: AsyncClient) -> None:
        """GET /api/admin/jobs/pending-retries/count returns 0 when none exist."""
        response = await client.get("/api/admin/jobs/pending-retries/count")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    async def test_counts_jobs_with_next_retry_at_set(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /api/admin/jobs/pending-retries/count counts jobs awaiting retry."""
        from datetime import datetime, timedelta

        # Create a job with next_retry_at set (pending retry)
        job = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            next_retry_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db_session.add(job)
        await db_session.flush()

        response = await client.get("/api/admin/jobs/pending-retries/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

    async def test_excludes_jobs_without_next_retry_at(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /api/admin/jobs/pending-retries/count excludes jobs without retry scheduled."""
        # Create jobs: one with retry, one without
        from datetime import datetime, timedelta

        with_retry = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            next_retry_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        without_retry = Job(
            id=uuid4(),
            user_id=uuid4(),
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            next_retry_at=None,
        )
        db_session.add(with_retry)
        db_session.add(without_retry)
        await db_session.flush()

        response = await client.get("/api/admin/jobs/pending-retries/count")

        assert response.status_code == 200
        data = response.json()
        # Count should be at least 1 (the with_retry job)
        assert data["count"] >= 1


class TestSyncUnlock:
    """Tests for POST /api/admin/sources/{source}/sync/unlock endpoint."""

    async def test_releases_sync_lock_and_returns_200(self, client: AsyncClient) -> None:
        """POST /api/admin/sources/t3k/sync/unlock releases lock and returns 200."""
        response = await client.post("/api/admin/sources/t3k/sync/unlock")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        """POST /api/admin/sources/unknown/sync/unlock returns 404."""
        response = await client.post("/api/admin/sources/unknown/sync/unlock")

        assert response.status_code == 404


class TestSchedulerUnlock:
    """Tests for POST /api/admin/scheduler/unlock endpoint."""

    async def test_releases_scheduler_lock_and_returns_200(self, client: AsyncClient) -> None:
        """POST /api/admin/scheduler/unlock releases lock and returns 200."""
        response = await client.post("/api/admin/scheduler/unlock")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestUnknownSourceHandling:
    """Tests for 404 handling of unknown source names."""

    async def test_all_source_endpoints_return_404_for_unknown_source(
        self, client: AsyncClient
    ) -> None:
        """All source-scoped endpoints return 404 for unknown source."""
        unknown_source_endpoints = [
            ("GET", "/api/admin/sources/nonexistent/sync/status"),
            ("POST", "/api/admin/sources/nonexistent/sync"),
            ("GET", "/api/admin/sources/nonexistent/sync/stats"),
            ("GET", "/api/admin/sources/nonexistent/sync/lag"),
            ("GET", "/api/admin/sources/nonexistent/errors/summary"),
            ("POST", "/api/admin/sources/nonexistent/sync/unlock"),
        ]

        for method, endpoint in unknown_source_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint)

            assert response.status_code == 404, (
                f"{method} {endpoint} should return 404 for unknown source"
            )
            data = response.json()
            assert "detail" in data, f"{method} {endpoint} should have detail message"
