"""Integration tests for T127: Waveform + Audio Metadata Extraction on Upload.

Tests that the DI track upload flow extracts and persists audio metadata
(channels, waveform) and that the API response includes this data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.services.di_track_service import DITrackService

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for upload tests."""
    user = User(
        id=uuid4(),
        username="waveform_testuser",
        email="waveform@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def _create_minimal_wav(path: Path) -> Path:
    """Create a minimal WAV file that can be read by soundfile.

    Creates a short silence file (0.1 seconds) with valid PCM data.
    """
    import numpy as np
    import soundfile as sf

    # Create 0.1 seconds of silence at 44.1kHz
    sample_rate = 44100
    duration = 0.1
    samples = int(sample_rate * duration)
    audio = np.zeros(samples, dtype=np.float32)

    sf.write(str(path), audio, sample_rate)
    return path


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackMetadataExtraction:
    """Integration: upload WAV file -> metadata populated in DB."""

    async def test_upload_populates_channels_in_database(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """AC: On upload, DITrackService extracts channels and stores in record."""
        audio_file = _create_minimal_wav(tmp_path / "channels_test.wav")
        service = DITrackService(db_session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="channels_test.wav",
            name="Channels Integration Test",
        )

        # Verify channels is persisted in database
        result = await db_session.execute(select(DITrack).where(DITrack.id == track.id))
        db_track = result.scalar_one()
        assert db_track.channels is not None
        assert isinstance(db_track.channels, int)
        assert db_track.channels >= 1

    async def test_upload_populates_waveform_in_database(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """AC: On upload, waveform data extracted and stored for visualisation."""
        audio_file = _create_minimal_wav(tmp_path / "waveform_test.wav")
        service = DITrackService(db_session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="waveform_test.wav",
            name="Waveform Integration Test",
        )

        # Verify waveform data is persisted in database
        result = await db_session.execute(select(DITrack).where(DITrack.id == track.id))
        db_track = result.scalar_one()
        assert db_track.waveform is not None

    async def test_upload_preserves_existing_metadata_alongside_waveform(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Existing metadata (duration, sample_rate) still present with waveform."""
        audio_file = _create_minimal_wav(tmp_path / "combined_test.wav")
        service = DITrackService(db_session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="combined_test.wav",
            name="Combined Metadata Test",
            description="Full metadata",
            guitar="Gibson LP",
        )

        # All metadata fields should be populated
        assert track.duration_seconds is not None
        assert track.duration_seconds > 0
        assert track.sample_rate is not None
        assert track.sample_rate > 0
        assert track.channels is not None
        assert track.name == "Combined Metadata Test"
        assert track.description == "Full metadata"
        assert track.guitar == "Gibson LP"


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackGracefulFallback:
    """AC: Extraction errors do not block upload (graceful fallback)."""

    async def test_waveform_failure_still_creates_track(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """If waveform extraction fails, track is still created with waveform=None."""
        # Minimal valid-header file that cannot be fully read for waveform
        audio_file = tmp_path / "tiny_fallback.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        service = DITrackService(db_session)

        # Should NOT raise — upload succeeds, metadata may be null
        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="tiny_fallback.wav",
            name="Fallback Track",
        )

        assert track is not None
        assert track.id is not None
        assert track.name == "Fallback Track"

        # Verify the record exists in database
        result = await db_session.execute(select(DITrack).where(DITrack.id == track.id))
        db_track = result.scalar_one()
        assert db_track is not None


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResponseIncludesMetadata:
    """AC: Metadata returned in API response (channels, waveform)."""

    async def test_response_schema_includes_channels(self) -> None:
        """DITrackResponse schema should include channels field."""
        from webapp.api.v1.schemas.di_track import DITrackResponse

        fields = DITrackResponse.model_fields
        assert (
            "channels" in fields
        ), "DITrackResponse must include 'channels' field for audio metadata"

    async def test_response_schema_includes_waveform(self) -> None:
        """DITrackResponse schema should include waveform field."""
        from webapp.api.v1.schemas.di_track import DITrackResponse

        fields = DITrackResponse.model_fields
        assert (
            "waveform" in fields
        ), "DITrackResponse must include 'waveform' field for visualisation data"
