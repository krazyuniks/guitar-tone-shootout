"""Integration tests for shootout metrics API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.metrics import router

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def completed_shootout(db_session: AsyncSession, test_user: User) -> dict:
    """Create a completed shootout with chains and segments."""
    di_track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI",
        file_path="/tmp/test.wav",
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=44100,
    )
    db_session.add(di_track)
    await db_session.flush()

    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.COMPLETED,
        output_path="/tmp/master.flac",
    )
    db_session.add(shootout)
    await db_session.flush()

    sc1 = SignalChain(id=uuid4(), user_id=test_user.id, name="Mesa Mark V", platform=Platform.NAM)
    sc2 = SignalChain(id=uuid4(), user_id=test_user.id, name="Fender Twin", platform=Platform.NAM)
    db_session.add_all([sc1, sc2])
    await db_session.flush()

    chain1 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=sc1.id,
        position=0,
        label="A",
    )
    chain2 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=sc2.id,
        position=1,
        label="B",
    )
    db_session.add_all([chain1, chain2])
    await db_session.flush()

    seg1 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain1.id,
        file_path="/tmp/seg1.flac",
        duration_seconds=10.0,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    seg2 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain2.id,
        file_path="/tmp/seg2.flac",
        duration_seconds=10.0,
        integrated_lufs=-16.0,
        peak_dbfs=-2.0,
    )
    db_session.add_all([seg1, seg2])
    await db_session.commit()

    return {
        "shootout": shootout,
        "chain1": chain1,
        "chain2": chain2,
        "sc1": sc1,
        "sc2": sc2,
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestMetadataEndpoint:
    """Tests for GET /api/shootouts/{id}/metadata."""

    async def test_metadata_returns_chain_configs(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/shootouts/{sid}/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["shootout_id"] == str(sid)
        assert len(data["chains"]) == 2
        assert data["chains"][0]["signal_chain_name"] == "Mesa Mark V"
        assert data["audio_settings"]["sample_rate"] == 44100

    async def test_metadata_returns_404_for_other_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from webapp.auth.dependencies import set_user_override

        other = User(id=uuid4(), username="other", email="other@test.com")
        db_session.add(other)
        await db_session.flush()
        set_user_override(other)
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/shootouts/{sid}/metadata")
        assert response.status_code == 404
        # Restore original user
        set_user_override(test_user)


@pytest.mark.asyncio
@pytest.mark.integration
class TestComparisonEndpoint:
    """Tests for GET /api/shootouts/{id}/comparison."""

    async def test_comparison_returns_all_segments_with_averages(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/shootouts/{sid}/comparison")
        assert response.status_code == 200
        data = response.json()
        assert len(data["segments"]) == 2
        assert data["averages"]["avg_integrated_lufs"] == -15.0
        assert data["averages"]["avg_peak_dbfs"] == -1.5


@pytest.mark.asyncio
@pytest.mark.integration
class TestSegmentMetricsEndpoint:
    """Tests for GET /api/shootouts/{id}/segments/{position}/metrics."""

    async def test_segment_metrics_returns_metrics_for_position(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/shootouts/{sid}/segments/0/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["position"] == 0
        assert data["metrics"]["integrated_lufs"] == -14.0

    async def test_segment_metrics_returns_404_for_invalid_position(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/shootouts/{sid}/segments/99/metrics")
        assert response.status_code == 404
