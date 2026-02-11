"""Unit tests for T127: Waveform + Audio Metadata Extraction on Upload.

Tests that DITrackService extracts channels, waveform data, and handles
extraction errors gracefully during upload.
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.services.di_track_service import DITrackService


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _create_minimal_wav(path: Path, *, channels: int = 1) -> Path:
    """Create a minimal but valid WAV file that can be read by soundfile.

    Creates a short silence file (0.1 seconds) with valid PCM data.
    """
    import numpy as np
    import soundfile as sf

    # Create 0.1 seconds of silence at 44.1kHz
    sample_rate = 44100
    duration = 0.1
    samples = int(sample_rate * duration)
    audio = np.zeros((samples, channels), dtype=np.float32)

    sf.write(str(path), audio, sample_rate)
    return path


class TestDITrackServiceChannelsExtraction:
    """Tests that DITrackService extracts channel count on upload."""

    async def test_upload_populates_channels(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload should populate the channels field on the DITrack record."""
        audio_file = _create_minimal_wav(tmp_path / "test.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Channels Test",
        )

        # channels should be extracted and stored (not None)
        assert track.channels is not None
        assert isinstance(track.channels, int)
        assert track.channels >= 1


class TestDITrackServiceWaveformExtraction:
    """Tests that DITrackService extracts waveform data on upload."""

    async def test_upload_populates_waveform(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload should extract and store waveform data for visualisation."""
        audio_file = _create_minimal_wav(tmp_path / "test.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Waveform Test",
        )

        # Waveform data should be populated after upload
        assert track.waveform is not None

    async def test_upload_waveform_has_peaks(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Waveform data should contain peak values for visualisation."""
        audio_file = _create_minimal_wav(tmp_path / "test.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test.wav",
            name="Peaks Test",
        )

        # If waveform is populated, it should have peaks
        if track.waveform is not None:
            assert hasattr(track.waveform, "peaks")
            assert isinstance(track.waveform.peaks, list | tuple)


class TestDITrackServiceGracefulFallback:
    """Tests that extraction errors do not block upload (graceful fallback)."""

    async def test_waveform_extraction_failure_does_not_block_upload(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """If waveform extraction fails, upload should still succeed with waveform=None."""
        # Create a file that has valid WAV header but is too small for waveform extraction
        audio_file = tmp_path / "tiny.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        service = DITrackService(session)

        # Upload should NOT raise — it should succeed with waveform as None
        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="tiny.wav",
            name="Fallback Test",
        )

        assert track is not None
        assert track.id is not None
        assert track.name == "Fallback Test"
        # Metadata should still be present even if waveform failed
        assert track.duration_seconds is not None
        assert track.sample_rate is not None
