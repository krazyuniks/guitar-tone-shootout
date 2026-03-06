"""Integration tests for DI track upload API endpoints."""

from __future__ import annotations

import io
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
async def existing_di_track(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> DITrack:
    """Create an existing DI track for the test user."""
    from gts.domain.value_objects.audio_checksum import AudioChecksum

    # Create a minimal audio file
    audio_file = tmp_path / "existing.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Existing Track",
        file_path=str(audio_file),
        original_filename="existing.wav",
        duration_seconds=1.0,
        sample_rate=44100,
        checksum=AudioChecksum.from_file(audio_file),
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)
    return track


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackUploadEndpoint:
    """Tests for POST /api/di-tracks endpoint."""

    async def test_upload_creates_track_returns_201(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test uploading a DI track returns 201 with DITrackResponse."""
        from fastapi import FastAPI

        # Create test audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        # Prepare multipart upload
        files = {
            "file": ("test.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {
            "name": "My DI Track",
            "description": "Test recording",
            "guitar": "Fender Strat",
            "pickup": "Bridge",
        }

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        # Should return 201 Created
        assert response.status_code == 201

        # Should return DITrackResponse schema
        json = response.json()
        assert json["name"] == "My DI Track"
        assert json["description"] == "Test recording"
        assert json["guitar"] == "Fender Strat"
        assert json["pickup"] == "Bridge"
        assert json["original_filename"] == "test.wav"
        assert "id" in json
        assert "user_id" in json
        assert "created_at" in json
        assert "duration_seconds" in json
        assert "sample_rate" in json

        # Verify database record exists
        from sqlalchemy import select

        result = await db_session.execute(select(DITrack).where(DITrack.name == "My DI Track"))
        track = result.scalar_one_or_none()
        assert track is not None
        assert track.user_id == test_user.id

    async def test_upload_requires_authentication(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test upload endpoint requires CurrentUser authentication."""
        from fastapi import FastAPI

        from webapp.auth.dependencies import set_user_override

        # Clear user override to simulate unauthenticated request
        set_user_override(None)

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("test.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {"name": "Test Track"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        # Should return 401 Unauthorized
        assert response.status_code == 401

    async def test_upload_saves_file_to_correct_path(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test file is saved to /app/storage/uploads/di_tracks/{user_id}/{uuid}.{ext}."""
        from fastapi import FastAPI

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("test.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {"name": "Test Track"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        # Check file path matches pattern
        json = response.json()
        assert "file_path" in json
        file_path = json["file_path"]

        # Path should be: /app/storage/uploads/di_tracks/{user_id}/{uuid}.wav
        assert file_path.startswith("/app/storage/uploads/di_tracks/")
        assert str(test_user.id) in file_path
        assert file_path.endswith(".wav")

    async def test_upload_rejects_invalid_format(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test upload returns 400 for invalid audio format."""
        from fastapi import FastAPI

        # Create non-audio file
        text_file = tmp_path / "not_audio.txt"
        text_file.write_text("This is not an audio file")

        files = {
            "file": ("not_audio.txt", io.BytesIO(text_file.read_bytes()), "text/plain"),
        }
        data = {"name": "Invalid Track"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "format" in response.json()["detail"].lower()

    async def test_upload_rejects_empty_name(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test upload returns 400 for empty track name."""
        from fastapi import FastAPI

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("test.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {"name": ""}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "name" in response.json()["detail"].lower()

    async def test_upload_rejects_duplicate_checksum(
        self,
        db_session: AsyncSession,
        test_user: User,
        existing_di_track: DITrack,
        tmp_path: Path,
    ) -> None:
        """Test upload returns 400 for duplicate audio file (same checksum)."""
        from fastapi import FastAPI

        # Use the same file as existing track
        audio_file = Path(existing_di_track.file_path)

        files = {
            "file": ("duplicate.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {"name": "Duplicate Track"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/di-tracks",
                files=files,
                data=data,
            )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackListEndpoint:
    """Tests for GET /api/di-tracks endpoint."""

    async def test_list_returns_current_user_tracks(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        tmp_path: Path,
    ) -> None:
        """Test GET /api/di-tracks lists only current user's tracks."""
        from fastapi import FastAPI

        # Create tracks for test_user
        track1 = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="User Track 1",
            file_path=str(tmp_path / "user1.wav"),
            original_filename="user1.wav",
            duration_seconds=10.0,
            sample_rate=44100,
        )
        track2 = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="User Track 2",
            file_path=str(tmp_path / "user2.wav"),
            original_filename="user2.wav",
            duration_seconds=20.0,
            sample_rate=48000,
        )

        # Create track for other_user
        other_track = DITrack(
            id=uuid4(),
            user_id=other_user.id,
            name="Other Track",
            file_path=str(tmp_path / "other.wav"),
            original_filename="other.wav",
            duration_seconds=15.0,
            sample_rate=44100,
        )

        db_session.add_all([track1, track2, other_track])
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/di-tracks")

        assert response.status_code == 200

        # Should only return test_user's tracks
        json = response.json()
        assert len(json) == 2
        names = {track["name"] for track in json}
        assert names == {"User Track 1", "User Track 2"}

    async def test_list_requires_authentication(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test list endpoint requires CurrentUser authentication."""
        from fastapi import FastAPI

        from webapp.auth.dependencies import set_user_override

        # Clear user override
        set_user_override(None)

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/di-tracks")

        assert response.status_code == 401

    async def test_list_supports_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test list endpoint supports limit and offset pagination."""
        from fastapi import FastAPI

        # Create 5 tracks
        for i in range(5):
            track = DITrack(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Track {i}",
                file_path=str(tmp_path / f"track{i}.wav"),
                original_filename=f"track{i}.wav",
                duration_seconds=10.0,
                sample_rate=44100,
            )
            db_session.add(track)
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Get first 2 tracks
            response = await client.get("/api/di-tracks?limit=2&offset=0")

        assert response.status_code == 200
        json = response.json()
        assert len(json) == 2


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackGetEndpoint:
    """Tests for GET /api/di-tracks/{id} endpoint."""

    async def test_get_returns_single_track(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test GET /api/di-tracks/{id} returns single track."""
        from fastapi import FastAPI

        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Track",
            file_path=str(tmp_path / "test.wav"),
            original_filename="test.wav",
            duration_seconds=10.0,
            sample_rate=44100,
            description="Test description",
            guitar="Fender Strat",
            pickup="Bridge",
        )
        db_session.add(track)
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{track.id}")

        assert response.status_code == 200

        json = response.json()
        assert json["id"] == str(track.id)
        assert json["name"] == "Test Track"
        assert json["description"] == "Test description"
        assert json["guitar"] == "Fender Strat"
        assert json["pickup"] == "Bridge"

    async def test_get_requires_ownership(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        tmp_path: Path,
    ) -> None:
        """Test GET returns 404 for tracks owned by other users."""
        from fastapi import FastAPI

        # Create track owned by other_user
        other_track = DITrack(
            id=uuid4(),
            user_id=other_user.id,
            name="Other Track",
            file_path=str(tmp_path / "other.wav"),
            original_filename="other.wav",
            duration_seconds=10.0,
            sample_rate=44100,
        )
        db_session.add(other_track)
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # test_user tries to access other_user's track
            response = await client.get(f"/api/di-tracks/{other_track.id}")

        # Should return 404 (not 403) to avoid leaking existence
        assert response.status_code == 404

    async def test_get_returns_404_for_nonexistent_track(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET returns 404 for non-existent track ID."""
        from fastapi import FastAPI

        fake_id = uuid4()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{fake_id}")

        assert response.status_code == 404

    async def test_get_requires_authentication(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test get endpoint requires CurrentUser authentication."""
        from fastapi import FastAPI

        from webapp.auth.dependencies import set_user_override

        # Clear user override
        set_user_override(None)

        fake_id = uuid4()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/di-tracks/{fake_id}")

        assert response.status_code == 401
