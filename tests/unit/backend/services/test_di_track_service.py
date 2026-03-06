"""Unit tests for DITrackService.

Tests the service layer for DI track upload and validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.user import User


class TestDITrackService:
    """Tests for DITrackService upload and validation."""

    async def test_service_exists(self) -> None:
        """Verify DITrackService can be imported."""
        # This will fail because the service doesn't exist yet
        from webapp.services.di_track_service import DITrackService

        assert DITrackService is not None

    async def test_service_handles_upload(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service handles file upload and creates DITrack."""
        from webapp.services.di_track_service import DITrackService

        # Create a mock audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)  # Minimal WAV header

        service = DITrackService(session)

        # This should create a DITrack entity with checksum and duration
        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Test Track",
        )

        assert track is not None
        assert track.id is not None
        assert track.user_id == test_user.id
        assert track.name == "Test Track"
        assert track.original_filename == "test.wav"
        assert track.checksum is not None
        assert track.duration_seconds > 0

    async def test_service_validates_file_format(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service validates audio file format."""
        from webapp.services.di_track_service import DITrackService

        # Create an invalid file
        invalid_file = tmp_path / "not_audio.txt"
        invalid_file.write_text("This is not an audio file")

        service = DITrackService(session)

        # Should raise validation error for non-audio file
        with pytest.raises(ValueError, match="Invalid audio file"):
            await service.upload(
                user_id=test_user.id,
                file_path=str(invalid_file),
                original_filename="not_audio.txt",
                name="Invalid Track",
            )

    async def test_service_calculates_duration(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service calculates track duration from audio file."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Test Track",
        )

        # Duration should be calculated from file
        assert track.duration_seconds is not None
        assert track.duration_seconds >= 0

    async def test_service_generates_checksum(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service generates checksum for uploaded file."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Test Track",
        )

        # Checksum should be generated
        assert track.checksum is not None
        assert isinstance(track.checksum.value, str)
        assert len(track.checksum.value) > 0

    async def test_service_detects_duplicates(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service detects duplicate files by checksum."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = DITrackService(session)

        # Upload first time
        await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="First Upload",
        )

        # Try to upload same file again
        with pytest.raises(ValueError, match="duplicate"):
            await service.upload(
                user_id=test_user.id,
                file_path=str(audio_file),
                original_filename="test.wav",
                name="Second Upload",
            )

    async def test_service_validates_empty_name(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service rejects empty track names."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = DITrackService(session)

        # Should reject empty name
        with pytest.raises(ValueError, match="name"):
            await service.upload(
                user_id=test_user.id,
                file_path=str(audio_file),
                original_filename="test.wav",
                name="",
            )

    async def test_service_accepts_optional_fields(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Test service accepts optional metadata fields."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Test Track",
            description="A test recording",
            guitar="Fender Stratocaster",
            pickup="Bridge",
        )

        assert track.description == "A test recording"
        assert track.guitar == "Fender Stratocaster"
        assert track.pickup == "Bridge"
