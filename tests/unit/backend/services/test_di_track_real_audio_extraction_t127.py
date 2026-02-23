"""Unit tests for T127: Waveform + Metadata Extraction with real audio files.

Verifies that DITrackService extracts channels, waveform data, duration,
and sample_rate from actual WAV files (not minimal-header stubs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
import pytest
import soundfile as sf

from webapp.adapters.persistence.models.user import User
from webapp.services.di_track_service import DITrackService

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username=f"realaudiotestuser_{uuid4().hex[:8]}",
        email=f"realaudio_{uuid4().hex[:8]}@example.com",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _create_real_mono_wav(path: Path, *, duration: float = 1.0, sample_rate: int = 44100) -> Path:
    """Create a real mono WAV file with a sine wave."""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
    sf.write(str(path), audio, sample_rate)
    return path


def _create_real_stereo_wav(path: Path, *, duration: float = 1.0, sample_rate: int = 48000) -> Path:
    """Create a real stereo WAV file with sine waves."""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    left = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
    right = (np.sin(2 * np.pi * 880 * t) * 0.6).astype(np.float32)
    audio = np.stack([left, right], axis=1)
    sf.write(str(path), audio, sample_rate)
    return path


class TestDITrackRealAudioMetadataExtraction:
    """Tests that real audio files have correct metadata extracted on upload."""

    async def test_mono_wav_extracts_correct_duration(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a real 1s mono WAV -> duration_seconds should be ~1.0."""
        audio_file = _create_real_mono_wav(tmp_path / "mono.wav", duration=1.0)
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="mono.wav",
            name="Mono Duration Test",
        )

        assert abs(track.duration_seconds - 1.0) < 0.01

    async def test_mono_wav_extracts_correct_sample_rate(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a real WAV at 44100Hz -> sample_rate should be 44100."""
        audio_file = _create_real_mono_wav(tmp_path / "mono.wav", sample_rate=44100)
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="mono.wav",
            name="Sample Rate Test",
        )

        assert track.sample_rate == 44100

    async def test_mono_wav_extracts_channels_as_1(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a mono WAV -> channels should be 1."""
        audio_file = _create_real_mono_wav(tmp_path / "mono.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="mono.wav",
            name="Mono Channels Test",
        )

        assert track.channels == 1

    async def test_stereo_wav_extracts_channels_as_2(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a stereo WAV -> channels should be 2."""
        audio_file = _create_real_stereo_wav(tmp_path / "stereo.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="stereo.wav",
            name="Stereo Channels Test",
        )

        assert track.channels == 2

    async def test_real_wav_extracts_waveform_data(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a real WAV -> waveform should be a WaveformData with peaks."""
        from gts.domain.value_objects.waveform_data import WaveformData

        audio_file = _create_real_mono_wav(tmp_path / "waveform.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="waveform.wav",
            name="Waveform Real Audio Test",
        )

        assert track.waveform is not None
        assert isinstance(track.waveform, WaveformData)
        assert track.waveform.peak_count > 0
        assert track.waveform.sample_rate == 44100
        assert abs(track.waveform.duration_seconds - 1.0) < 0.01

    async def test_real_wav_waveform_peaks_have_nonzero_values(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Waveform peaks from a sine wave should not all be zero."""
        audio_file = _create_real_mono_wav(tmp_path / "peaks.wav")
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="peaks.wav",
            name="Peaks Non-Zero Test",
        )

        assert track.waveform is not None
        assert any(p != 0.0 for p in track.waveform.peaks)

    async def test_48khz_wav_extracts_correct_sample_rate(
        self,
        session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload a 48kHz WAV -> sample_rate should be 48000."""
        audio_file = _create_real_stereo_wav(tmp_path / "hd.wav", sample_rate=48000)
        service = DITrackService(session)

        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="hd.wav",
            name="48kHz Test",
        )

        assert track.sample_rate == 48000
