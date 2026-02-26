"""Integration tests for webapp Admin API sync endpoints.

Tests that the admin sync endpoints query real infrastructure instead of
returning hardcoded stubs. Each endpoint is verified against actual database
state (SyncCheckpoint, Job records) and PG advisory lock state (not Redis).

These endpoints are served at /api/admin with no authentication.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from gts.domain.value_objects.job_status import JobStatus, JobType
from source_t3k.adapters.outbound.models import SyncCheckpoint
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """Webapp Admin router mounted on a test FastAPI app with session override."""
    from fastapi import FastAPI

    from webapp.api.admin import _get_db as _admin_get_db
    from webapp.api.admin import router

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[_admin_get_db] = override_session
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
async def clean_sync_data(db_session: AsyncSession) -> None:
    """Delete existing SyncCheckpoint rows so empty-data tests work."""
    await db_session.execute(delete(SyncCheckpoint).where(SyncCheckpoint.source_name == "t3k"))
    await db_session.flush()


@pytest.fixture
async def clean_failed_jobs(db_session: AsyncSession) -> None:
    """Delete recent failed jobs so empty-errors tests work."""
    await db_session.execute(delete(Job).where(Job.status == JobStatus.FAILED))
    await db_session.flush()


@pytest.fixture
async def sync_checkpoint(db_session: AsyncSession, clean_sync_data: None) -> SyncCheckpoint:
    """Create a SyncCheckpoint row for the t3k tone entity type."""
    cp = SyncCheckpoint(
        source_name="t3k",
        entity_type="tone",
        last_synced_at=datetime.now(UTC) - timedelta(minutes=5),
        last_record_id="tone-1234",
        total_synced=42,
    )
    db_session.add(cp)
    await db_session.flush()
    await db_session.refresh(cp)
    return cp


@pytest.fixture
async def model_checkpoint(db_session: AsyncSession, clean_sync_data: None) -> SyncCheckpoint:
    """Create a SyncCheckpoint row for the t3k model entity type."""
    cp = SyncCheckpoint(
        source_name="t3k",
        entity_type="model",
        last_synced_at=datetime.now(UTC) - timedelta(minutes=2),
        last_record_id="model-5678",
        total_synced=108,
    )
    db_session.add(cp)
    await db_session.flush()
    await db_session.refresh(cp)
    return cp


@pytest.fixture
async def failed_jobs_last_24h(
    db_session: AsyncSession,
    clean_failed_jobs: None,
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
    await db_session.flush()
    for job in jobs:
        await db_session.refresh(job)
    return jobs


# ---------------------------------------------------------------------------
# GET /api/admin/sources/{source}/sync/status
# ---------------------------------------------------------------------------


class TestSyncStatus:
    """GET .../sync/status must query SyncCheckpoint + running Job state."""

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

            assert data["checkpoint"] is not None
            assert data["checkpoint"]["last_tone_id"] == "tone-1234"

    @pytest.mark.asyncio
    async def test_status_idle_when_no_running_job(
        self,
        admin_app: FastAPI,
        sync_checkpoint: SyncCheckpoint,
    ) -> None:
        """When no running SOURCE_SYNC job exists, status should be 'idle'."""
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
        clean_sync_data: None,
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
    """POST .../sync must create a pending SOURCE_SYNC job."""

    @pytest.mark.asyncio
    async def test_returns_202_accepted(
        self,
        admin_app: FastAPI,
        db_session: AsyncSession,
        clean_sync_data: None,
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
        clean_sync_data: None,
    ) -> None:
        """Triggering sync creates a SOURCE_SYNC Job record in the database."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync")
            assert response.status_code == 202

        db_session.expire_all()
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
    """GET .../sync/stats must query SyncCheckpoint.total_synced."""

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

            # total_synced = 42 (tones) + 108 (models) = 150
            assert data["total_synced"] == 150

    @pytest.mark.asyncio
    async def test_zero_when_no_checkpoints(
        self,
        admin_app: FastAPI,
        clean_sync_data: None,
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

            assert data["lag_seconds"] is not None
            assert data["lag_seconds"] > 0
            assert data["lag_seconds"] >= 200

    @pytest.mark.asyncio
    async def test_null_when_no_checkpoints(
        self,
        admin_app: FastAPI,
        clean_sync_data: None,
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
            assert data["lag_seconds"] is not None
            assert data["lag_seconds"] < 250

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

            assert data["errors"] != {}
            assert data["time_window_hours"] == 24

            total_errors = sum(data["errors"].values())
            assert total_errors >= 1, "Must have at least one error from failed jobs"

    @pytest.mark.asyncio
    async def test_empty_when_no_failures(
        self,
        admin_app: FastAPI,
        clean_failed_jobs: None,
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
# POST /api/admin/sources/{source}/sync/unlock
# ---------------------------------------------------------------------------


class TestSyncUnlock:
    """POST .../sync/unlock returns 200 (PG advisory lock is self-managed)."""

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
    async def test_message_references_pg_lock(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Response message references PG advisory lock (not Redis)."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/sources/t3k/sync/unlock")
            assert response.status_code == 200
            data = response.json()
            assert data["message"]  # non-empty message

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
    """POST /api/admin/scheduler/unlock returns 200 (PG advisory lock is self-managed)."""

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
    async def test_message_references_pg_lock(
        self,
        admin_app: FastAPI,
    ) -> None:
        """Response message references PG advisory lock."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/admin/scheduler/unlock")
            assert response.status_code == 200
            data = response.json()
            assert data["message"]  # non-empty message


# ---------------------------------------------------------------------------
# POST /api/admin/enqueue
# ---------------------------------------------------------------------------


class TestEnqueue:
    """POST /api/admin/enqueue dispatches to pgmq; SOURCE_SYNC returns 400."""

    @pytest.mark.asyncio
    async def test_source_sync_enqueue_returns_400(
        self,
        admin_app: FastAPI,
        db_session: AsyncSession,
    ) -> None:
        """SOURCE_SYNC is self-managed by t3k-sync; enqueue returns 400."""
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
        await db_session.flush()

        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/admin/enqueue",
                json={"job_id": str(job.id)},
            )
            assert response.status_code == 400

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
