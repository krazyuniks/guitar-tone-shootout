"""Integration tests for T3K sync admin API endpoints.

Tests that the admin sync endpoints query real infrastructure instead of
returning hardcoded stubs. Each endpoint is verified against actual database
state (SyncCheckpoint, Job records).

These endpoints are served at /api/admin with no authentication.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from source_t3k.adapters.outbound.models import SyncCheckpoint

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """T3K sync admin router mounted on a test FastAPI app with session override."""
    from fastapi import FastAPI

    from t3k_sync.api.admin import _get_db as _admin_get_db
    from t3k_sync.api.admin import router

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
