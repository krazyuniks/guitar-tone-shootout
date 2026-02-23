"""Integration tests for waveform extraction.

Tests waveform data extraction from real audio files.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio.analysis.waveform import extract_waveform
from gts.domain.value_objects.waveform_data import WaveformData  # type: ignore[import-untyped]


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    """Create a test audio file with known waveform."""
    # Create 1 second of sine wave at 440Hz
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)

    file_path = tmp_path / "test_audio.wav"
    sf.write(file_path, audio, sample_rate)
    return file_path


@pytest.fixture
def stereo_audio_file(tmp_path: Path) -> Path:
    """Create a test stereo audio file."""
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    # Left channel: 440Hz, Right channel: 880Hz
    left = np.sin(2 * np.pi * 440 * t)
    right = np.sin(2 * np.pi * 880 * t)
    audio = np.stack([left, right], axis=1)

    file_path = tmp_path / "stereo_audio.wav"
    sf.write(file_path, audio, sample_rate)
    return file_path


def test_extract_waveform_default_peaks(audio_file: Path) -> None:
    """Test waveform extraction with default number of peaks."""
    waveform = extract_waveform(audio_file)

    assert isinstance(waveform, WaveformData)
    assert waveform.peak_count == 200  # Default num_peaks
    assert waveform.sample_rate == 48000
    assert abs(waveform.duration_seconds - 1.0) < 0.01
    assert waveform.samples_per_peak == 48000 // 200


def test_extract_waveform_custom_peaks(audio_file: Path) -> None:
    """Test waveform extraction with custom number of peaks."""
    waveform = extract_waveform(audio_file, num_peaks=100)

    assert waveform.peak_count == 100
    assert waveform.samples_per_peak == 48000 // 100


def test_extract_waveform_peak_values(audio_file: Path) -> None:
    """Test that peak values are normalized and correct."""
    waveform = extract_waveform(audio_file, num_peaks=10)

    # Sine wave should have peaks close to ±1.0
    max_peak = max(abs(p) for p in waveform.peaks)
    assert 0.9 < max_peak <= 1.0  # Allow small margin


def test_extract_waveform_stereo(stereo_audio_file: Path) -> None:
    """Test waveform extraction from stereo audio."""
    waveform = extract_waveform(stereo_audio_file)

    assert isinstance(waveform, WaveformData)
    assert waveform.peak_count == 200
    # Should convert stereo to mono by averaging
    assert waveform.sample_rate == 48000


def test_extract_waveform_preserves_sign(tmp_path: Path) -> None:
    """Test that peak extraction preserves sign of loudest sample."""
    # Create audio with clear positive and negative segments
    # Each peak segment should contain only one sign
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)

    # With 10 peaks, each peak covers 4800 samples
    # Create segments of 4800 samples each, alternating between +0.8 and -0.8
    num_peaks = 10
    samples_per_segment = samples // num_peaks
    audio = np.zeros(samples)

    for i in range(num_peaks):
        start = i * samples_per_segment
        end = min((i + 1) * samples_per_segment, samples)
        # Alternate between positive and negative
        audio[start:end] = 0.8 if i % 2 == 0 else -0.8

    file_path = tmp_path / "alternating.wav"
    sf.write(file_path, audio, sample_rate)

    waveform = extract_waveform(file_path, num_peaks=num_peaks)

    # Should have both positive and negative peaks
    positive_peaks = [p for p in waveform.peaks if p > 0]
    negative_peaks = [p for p in waveform.peaks if p < 0]

    assert len(positive_peaks) > 0
    assert len(negative_peaks) > 0


def test_extract_waveform_with_silence(tmp_path: Path) -> None:
    """Test waveform extraction from silent audio."""
    # Create silent audio file
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio = np.zeros(samples)

    file_path = tmp_path / "silent.wav"
    sf.write(file_path, audio, sample_rate)

    waveform = extract_waveform(file_path)

    assert waveform.peak_count == 200
    # All peaks should be zero
    assert all(p == 0.0 for p in waveform.peaks)


def test_extract_waveform_short_audio(tmp_path: Path) -> None:
    """Test waveform extraction from audio shorter than num_peaks."""
    # Create very short audio (100 samples)
    sample_rate = 48000
    audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 100))

    file_path = tmp_path / "short.wav"
    sf.write(file_path, audio, sample_rate)

    waveform = extract_waveform(file_path, num_peaks=200)

    # Should return fewer peaks than requested
    assert waveform.peak_count <= 200
    assert waveform.peak_count > 0


def test_extract_waveform_nonexistent_file(tmp_path: Path) -> None:
    """Test that extract_waveform raises error for nonexistent file."""
    nonexistent = tmp_path / "does_not_exist.wav"

    with pytest.raises(FileNotFoundError):
        extract_waveform(nonexistent)
