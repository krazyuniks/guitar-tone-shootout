"""Integration tests for shootout audio streaming endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.shootouts import router, set_session_override, set_user_override

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def _wire_shootout_deps(db_session: AsyncSession, test_user: User) -> None:
    """Wire shootout module's local dependency overrides."""
    set_session_override(db_session)
    set_user_override(test_user)
    yield  # type: ignore[misc]
    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def completed_shootout(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> dict:
    """Create a completed shootout with master audio and chain segments."""
    # DI track
    di_file = tmp_path / f"{uuid4()}.wav"
    di_file.write_bytes(b"RIFF" + b"\x00" * 100)
    di_track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI",
        file_path=str(di_file),
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=44100,
    )
    db_session.add(di_track)
    await db_session.flush()

    # Master audio file
    master_file = tmp_path / "master.flac"
    master_file.write_bytes(b"fLaC" + b"\x00" * 100)

    # Shootout
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.COMPLETED,
        output_path=str(master_file),
    )
    db_session.add(shootout)
    await db_session.flush()

    # Signal chains
    sc1 = SignalChain(id=uuid4(), user_id=test_user.id, name="Chain 1", platform=Platform.NAM)
    sc2 = SignalChain(id=uuid4(), user_id=test_user.id, name="Chain 2", platform=Platform.NAM)
    db_session.add_all([sc1, sc2])
    await db_session.flush()

    # Shootout chains
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

    # Audio segments (one per chain)
    seg1_file = tmp_path / "seg1.flac"
    seg1_file.write_bytes(b"fLaC" + b"\x01" * 50)
    seg1 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain1.id,
        file_path=str(seg1_file),
        duration_seconds=10.0,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    seg2_file = tmp_path / "seg2.flac"
    seg2_file.write_bytes(b"fLaC" + b"\x02" * 50)
    seg2 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain2.id,
        file_path=str(seg2_file),
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
        "seg1": seg1,
        "seg2": seg2,
        "master_file": master_file,
        "seg1_file": seg1_file,
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestMasterAudioStream:
    """Tests for GET /api/v1/shootouts/{id}/audio/master."""

    async def test_stream_master_returns_flac(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/shootouts/{completed_shootout['shootout'].id}/audio/master",
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"
        assert response.content.startswith(b"fLaC")

    async def test_stream_master_returns_404_for_other_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        other = User(id=uuid4(), username="other", email="other@test.com")
        db_session.add(other)
        await db_session.flush()
        set_user_override(other)
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/shootouts/{completed_shootout['shootout'].id}/audio/master",
            )
        assert response.status_code == 404

    async def test_stream_master_returns_404_for_nonexistent(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{uuid4()}/audio/master")
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestChainAudioStream:
    """Tests for GET /api/v1/shootouts/{id}/chains/{chain_id}/audio."""

    async def test_stream_chain_audio_returns_flac(
        self,
        db_session: AsyncSession,
        test_user: User,
        completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        cid = completed_shootout["chain1"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/chains/{cid}/audio")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"

    async def test_stream_chain_audio_returns_404_for_wrong_chain(
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
            response = await client.get(f"/api/v1/shootouts/{sid}/chains/{uuid4()}/audio")
        assert response.status_code == 404
