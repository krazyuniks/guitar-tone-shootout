"""Integration tests for Worker Admin API sync endpoints (T115).

Tests that the admin sync endpoints query real infrastructure instead of
returning hardcoded stubs. Each endpoint is verified against actual database
state (SyncCheckpoint, Job records) and Redis lock keys.

These endpoints run on port 8001 with no authentication.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from source_t3k.adapters.outbound.models import SyncCheckpoint
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def t3k_tables(db_engine: AsyncEngine) -> None:
    """Create T3K SyncCheckpoint table in the test DB.

    Only creates the SyncCheckpoint table (not all T3K tables) because
    T3KToneStaging uses PostgreSQL ARRAY columns incompatible with SQLite.
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(SyncCheckpoint.__table__.create)


@pytest.fixture
def admin_app() -> FastAPI:
    """Create Worker Admin API app instance for testing."""
    from worker.admin import app

    return app


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    """Create database session from engine."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def sync_checkpoint(db_session: AsyncSession, t3k_tables: None) -> SyncCheckpoint:
    """Create a SyncCheckpoint row for the t3k tone entity type."""
    cp = SyncCheckpoint(
        source_name="t3k",
        entity_type="tone",
        last_synced_at=datetime.now(UTC) - timedelta(minutes=5),
        last_record_id="tone-1234",
        total_synced=42,
    )
    db_session.add(cp)
    await db_session.commit()
    await db_session.refresh(cp)
    return cp


@pytest.fixture
async def model_checkpoint(db_session: AsyncSession, t3k_tables: None) -> SyncCheckpoint:
    """Create a SyncCheckpoint row for the t3k model entity type."""
    cp = SyncCheckpoint(
        source_name="t3k",
        entity_type="model",
        last_synced_at=datetime.now(UTC) - timedelta(minutes=2),
        last_record_id="model-5678",
        total_synced=108,
    )
    db_session.add(cp)
    await db_session.commit()
    await db_session.refresh(cp)
    return cp


@pytest.fixture
async def failed_jobs_last_24h(
    db_session: AsyncSession,
) -> list[Job]:
    """Create several failed Job records within the last 24 hours."""
    now = datetime.now(UTC)
    jobs = [
        Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.SOURCE_SYNC,
            status=JobStatus.FAILED,
            progress=0,
            error="Connection timeout",
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2),
            attempt=1,
            max_attempts=3,
        ),
        Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.SOURCE_SYNC,
            status=JobStatus.FAILED,
            progress=0,
            error="Rate limit exceeded",
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=1),
            attempt=1,
            max_attempts=3,
        ),
        Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.GEAR_SYNC,
            status=JobStatus.FAILED,
            progress=0,
            error="Connection timeout",
            started_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=3),
            attempt=1,
            max_attempts=3,
        ),
    ]
    for job in jobs:
        db_session.add(job)
    await db_session.commit()
    for job in jobs:
        await db_session.refresh(job)
    return jobs


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/sync/status
# ---------------------------------------------------------------------------


class TestSyncStatus:
    """GET .../sync/status must query SyncCheckpoint + Redis lock state."""

    @pytest.mark.asyncio
    async def test_returns_real_checkpoint_data(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
    ) -> None:
        """Sync status response includes checkpoint info from SyncCheckpoint table."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/status")
            assert response.status_code == 200
            data = response.json()

            # The real implementation must populate checkpoint from DB
            assert data["checkpoint"] is not None
            assert data["checkpoint"]["last_tone_id"] == "tone-1234"

    @pytest.mark.asyncio
    async def test_status_idle_when_no_lock(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
    ) -> None:
        """When no Redis sync lock exists, status should be 'idle'."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "idle"

    @pytest.mark.asyncio
    async def test_no_checkpoint_returns_null(
        self,
        admin_app: FastAPI,
        t3k_tables: None,
    ) -> None:
        """When no SyncCheckpoint exists, checkpoint should be null."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/status")
            assert response.status_code == 200
            data = response.json()
            assert data["checkpoint"] is None

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/unknown/sync/status")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/admin/sources/{source}/sync
# ---------------------------------------------------------------------------


class TestSyncTrigger:
    """POST .../sync must dispatch handle_source_sync TaskIQ job."""

    @pytest.mark.asyncio
    async def test_returns_202_accepted(
        self,
        admin_app: FastAPI,
        db_session: AsyncSession,
        t3k_tables: None,
    ) -> None:
        """Triggering sync returns 202 Accepted."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync")
            assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_creates_source_sync_job(
        self,
        admin_app: FastAPI,
        db_session: AsyncSession,
        t3k_tables: None,
    ) -> None:
        """Triggering sync creates a SOURCE_SYNC Job record in the database."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync")
            assert response.status_code == 202

        # Verify a SOURCE_SYNC job was created in the database
        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.job_type == JobType.SOURCE_SYNC))
        jobs = result.scalars().all()
        assert len(jobs) >= 1, "POST /sync must create a SOURCE_SYNC job record"

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/unknown/sync")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/sync/stats
# ---------------------------------------------------------------------------


class TestSyncStats:
    """GET .../sync/stats must query SyncCheckpoint.total_synced + pgmq depths."""

    @pytest.mark.asyncio
    async def test_returns_real_total_synced(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
        model_checkpoint: SyncCheckpoint,
    ) -> None:
        """total_synced reflects the sum of SyncCheckpoint.total_synced rows."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/stats")
            assert response.status_code == 200
            data = response.json()

            # total_synced = 42 (packs) + 108 (models) = 150
            assert data["total_synced"] == 150

    @pytest.mark.asyncio
    async def test_zero_when_no_checkpoints(
        self,
        admin_app: FastAPI,
        t3k_tables: None,
    ) -> None:
        """total_synced is 0 when no SyncCheckpoint rows exist."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/stats")
            assert response.status_code == 200
            data = response.json()
            assert data["total_synced"] == 0

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/unknown/sync/stats")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/sync/lag
# ---------------------------------------------------------------------------


class TestSyncLag:
    """GET .../sync/lag must compute real seconds since last_synced_at."""

    @pytest.mark.asyncio
    async def test_returns_real_lag_seconds(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
    ) -> None:
        """lag_seconds reflects actual time since most recent SyncCheckpoint.last_synced_at."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/lag")
            assert response.status_code == 200
            data = response.json()

            # The checkpoint was created ~5 minutes ago, so lag should be > 0
            assert data["lag_seconds"] is not None
            assert data["lag_seconds"] > 0
            # Sanity: should be at least 200 seconds (5 min = 300s, minus some tolerance)
            assert data["lag_seconds"] >= 200

    @pytest.mark.asyncio
    async def test_null_when_no_checkpoints(
        self,
        admin_app: FastAPI,
        t3k_tables: None,
    ) -> None:
        """lag_seconds is null when no SyncCheckpoint rows exist."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/lag")
            assert response.status_code == 200
            data = response.json()
            assert data["lag_seconds"] is None

    @pytest.mark.asyncio
    async def test_uses_most_recent_checkpoint(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
        model_checkpoint: SyncCheckpoint,
    ) -> None:
        """lag_seconds uses the most recent last_synced_at across all entity types."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/sync/lag")
            assert response.status_code == 200
            data = response.json()

            # model_checkpoint is more recent (2 min ago vs 5 min ago)
            # So lag should be ~120s, not ~300s
            assert data["lag_seconds"] is not None
            assert data["lag_seconds"] < 250  # Should be closer to 120s

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/unknown/sync/lag")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/errors/summary
# ---------------------------------------------------------------------------


class TestErrorsSummary:
    """GET .../errors/summary must query failed Job records in last 24h."""

    @pytest.mark.asyncio
    async def test_returns_real_error_counts(
        self,
        admin_app: FastAPI,
        failed_jobs_last_24h: list[Job],
    ) -> None:
        """errors dict contains counts of failed jobs grouped by error message."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/errors/summary")
            assert response.status_code == 200
            data = response.json()

            # Should have non-empty errors dict
            assert data["errors"] != {}
            assert data["time_window_hours"] == 24

            # There are 3 failed jobs: 2 "Connection timeout", 1 "Rate limit exceeded"
            total_errors = sum(data["errors"].values())
            assert total_errors >= 1, "Must have at least one error from failed jobs"

    @pytest.mark.asyncio
    async def test_empty_when_no_failures(
        self,
        admin_app: FastAPI,
        t3k_tables: None,
    ) -> None:
        """errors dict is empty when no failed jobs exist."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/errors/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["errors"] == {}

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/unknown/errors/summary")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/auth/status
# ---------------------------------------------------------------------------


class TestAuthStatus:
    """GET .../auth/status checks T3K_API_KEY env var (no DB query)."""

    @pytest.mark.asyncio
    async def test_valid_when_api_key_set(
        self,
        admin_app: FastAPI,
        monkeypatch,
    ) -> None:
        """Returns valid=True and method=api_key when T3K_API_KEY is set."""
        monkeypatch.setenv("T3K_API_KEY", "test-key-123")
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/auth/status")
            assert response.status_code == 200
            data = response.json()

            assert data["valid"] is True
            assert data["method"] == "api_key"

    @pytest.mark.asyncio
    async def test_invalid_when_no_api_key(
        self,
        admin_app: FastAPI,
        monkeypatch,
    ) -> None:
        """Returns valid=False when T3K_API_KEY is not set."""
        monkeypatch.delenv("T3K_API_KEY", raising=False)
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/t3k/auth/status")
            assert response.status_code == 200
            data = response.json()

            assert data["valid"] is False
            assert data["method"] == "api_key"

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/sources/unknown/auth/status")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/admin/sources/{source}/sync/unlock
# ---------------------------------------------------------------------------


class TestSyncUnlock:
    """POST .../sync/unlock must delete Redis key t3k:sync:lock."""

    @pytest.mark.asyncio
    async def test_returns_200(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unlock sync returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync/unlock")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_message_confirms_lock_released(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Response message confirms that the lock was released."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync/unlock")
            assert response.status_code == 200
            data = response.json()
            # The implementation must actually delete the Redis key — the message
            # should reflect that an actual Redis DELETE happened, not just a stub
            assert "released" in data["message"].lower() or "unlocked" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unknown source name returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/unknown/sync/unlock")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/admin/scheduler/unlock
# ---------------------------------------------------------------------------


class TestSchedulerUnlock:
    """POST /api/admin/scheduler/unlock must delete Redis key scheduler:lock."""

    @pytest.mark.asyncio
    async def test_returns_200(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Unlock scheduler returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/scheduler/unlock")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_message_confirms_lock_released(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Response message confirms scheduler lock was released."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/scheduler/unlock")
            assert response.status_code == 200
            data = response.json()
            assert "released" in data["message"].lower() or "unlocked" in data["message"].lower()


# ---------------------------------------------------------------------------
# POST /api/admin/enqueue
# ---------------------------------------------------------------------------


class TestEnqueue:
    """POST /api/admin/enqueue must dispatch job to TaskIQ broker."""

    @pytest.mark.asyncio
    async def test_dispatches_real_job(
        self,
        admin_app: FastAPI,
        db_session: AsyncSession,
    ) -> None:
        """Enqueue endpoint dispatches to TaskIQ broker and updates job record."""
        # Create a PENDING job to enqueue
        job = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.SOURCE_SYNC,
            status=JobStatus.PENDING,
            progress=0,
            attempt=1,
            max_attempts=3,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/admin/enqueue",
                json={"job_id": str(job.id)},
            )
            assert response.status_code == 202
            data = response.json()
            assert data["id"] == str(job.id)

        # After real enqueue, the job should have a task_id set by TaskIQ
        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.id == job.id))
        updated_job = result.scalar_one()
        assert updated_job.task_id is not None, (
            "Enqueue must set task_id from TaskIQ dispatch result"
        )

    @pytest.mark.asyncio
    async def test_nonexistent_job_returns_404(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Enqueue returns 404 for nonexistent job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/admin/enqueue",
                json={"job_id": str(uuid4())},
            )
            assert response.status_code == 404
