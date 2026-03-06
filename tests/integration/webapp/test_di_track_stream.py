"""Integration tests for DI track stream API endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.di_tracks import router

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another user for ownership tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def wav_track(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create a DI track with .wav format."""
    # Create minimal WAV file
    audio_file = tmp_path / f"{uuid4()}.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="WAV Track",
        file_path=str(audio_file),
        original_filename="test.wav",
        duration_seconds=1.0,
        sample_rate=44100,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def flac_track(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create a DI track with .flac format."""
    # Create minimal FLAC file
    audio_file = tmp_path / f"{uuid4()}.flac"
    audio_file.write_bytes(b"fLaC" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="FLAC Track",
        file_path=str(audio_file),
        original_filename="test.flac",
        duration_seconds=1.0,
        sample_rate=44100,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def ogg_track(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create a DI track with .ogg format."""
    # Create minimal OGG file
    audio_file = tmp_path / f"{uuid4()}.ogg"
    audio_file.write_bytes(b"OggS" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="OGG Track",
        file_path=str(audio_file),
        original_filename="test.ogg",
        duration_seconds=1.0,
        sample_rate=44100,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def mp3_track(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create a DI track with .mp3 format."""
    # Create minimal MP3 file (ID3v2 header)
    audio_file = tmp_path / f"{uuid4()}.mp3"
    audio_file.write_bytes(b"ID3" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="MP3 Track",
        file_path=str(audio_file),
        original_filename="test.mp3",
        duration_seconds=1.0,
        sample_rate=44100,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def other_user_track(
    db_session: AsyncSession,
    other_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create a DI track owned by other_user."""
    audio_file = tmp_path / f"{uuid4()}.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Track",
        file_path=str(audio_file),
        original_filename="other.wav",
        duration_seconds=1.0,
        sample_rate=44100,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackStreamEndpoint:
    """Tests for GET /api/di-tracks/{id}/stream endpoint."""

    async def test_stream_wav_returns_correct_content_type(
        self,
        db_session: AsyncSession,
        test_user: User,
        wav_track: DITrack,
    ) -> None:
        """Test streaming .wav file returns Content-Type: audio/wav."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{wav_track.id}/stream")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        # Verify actual file content is returned
        assert len(response.content) > 0

    async def test_stream_flac_returns_correct_content_type(
        self,
        db_session: AsyncSession,
        test_user: User,
        flac_track: DITrack,
    ) -> None:
        """Test streaming .flac file returns Content-Type: audio/flac."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{flac_track.id}/stream")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"
        assert len(response.content) > 0

    async def test_stream_ogg_returns_correct_content_type(
        self,
        db_session: AsyncSession,
        test_user: User,
        ogg_track: DITrack,
    ) -> None:
        """Test streaming .ogg file returns Content-Type: audio/ogg."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{ogg_track.id}/stream")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/ogg"
        assert len(response.content) > 0

    async def test_stream_mp3_returns_correct_content_type(
        self,
        db_session: AsyncSession,
        test_user: User,
        mp3_track: DITrack,
    ) -> None:
        """Test streaming .mp3 file returns Content-Type: audio/mpeg."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{mp3_track.id}/stream")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert len(response.content) > 0

    async def test_stream_owner_can_access_track(
        self,
        db_session: AsyncSession,
        test_user: User,
        wav_track: DITrack,
    ) -> None:
        """Test track owner can stream their own tracks."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{wav_track.id}/stream")

        assert response.status_code == 200
        # Verify file content matches what we wrote
        assert response.content.startswith(b"RIFF")

    async def test_stream_returns_404_for_other_user_track(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user_track: DITrack,
    ) -> None:
        """Test streaming returns 404 for tracks owned by other users (avoids leaking existence)."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # test_user tries to stream other_user's track
            response = await client.get(f"/api/di-tracks/{other_user_track.id}/stream")

        # Should return 404, not 403, to avoid leaking existence
        assert response.status_code == 404

    async def test_stream_returns_404_for_nonexistent_track(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test streaming returns 404 for non-existent track ID."""
        from fastapi import FastAPI

        fake_id = uuid4()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{fake_id}/stream")

        assert response.status_code == 404

    async def test_stream_requires_authentication(
        self,
        db_session: AsyncSession,
        wav_track: DITrack,
    ) -> None:
        """Test stream endpoint requires authentication."""
        from fastapi import FastAPI

        from webapp.auth.dependencies import set_user_override

        # Clear user override to simulate unauthenticated request
        set_user_override(None)

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{wav_track.id}/stream")

        # Should return 401 Unauthorized
        assert response.status_code == 401

    async def test_stream_returns_file_response_with_headers(
        self,
        db_session: AsyncSession,
        test_user: User,
        wav_track: DITrack,
    ) -> None:
        """Test stream returns FileResponse with correct headers for audio streaming."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{wav_track.id}/stream")

        assert response.status_code == 200

        # Verify FileResponse headers
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "audio/wav"

        # Verify content-length is set (FileResponse auto-sets this)
        assert "content-length" in response.headers
        assert int(response.headers["content-length"]) > 0

        # Verify actual file content
        file_content = Path(wav_track.file_path).read_bytes()
        assert response.content == file_content
