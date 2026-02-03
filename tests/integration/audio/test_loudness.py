"""Integration tests for loudness normalization."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio.processing.loudness import (
    LoudnessError,
    measure_loudness,
    normalize_loudness,
)


@pytest.fixture
def test_audio_path(tmp_path: Path) -> Path:
    """Create a test audio file."""
    output_path = tmp_path / "test.wav"
    sample_rate = 48000
    duration = 1.0  # 1 second
    samples = int(sample_rate * duration)

    # Generate sine wave at 440Hz with amplitude 0.5
    t = np.linspace(0, duration, samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)

    sf.write(output_path, audio, sample_rate)
    return output_path


@pytest.fixture
def silent_audio_path(tmp_path: Path) -> Path:
    """Create a silent audio file."""
    output_path = tmp_path / "silent.wav"
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)

    # All zeros
    audio = np.zeros(samples)

    sf.write(output_path, audio, sample_rate)
    return output_path


def test_measure_loudness_returns_tuple(test_audio_path: Path) -> None:
    """Test that measure_loudness returns (integrated_lufs, peak_dbfs)."""
    integrated_lufs, peak_dbfs = measure_loudness(test_audio_path)

    assert isinstance(integrated_lufs, float)
    assert isinstance(peak_dbfs, float)
    assert integrated_lufs < 0  # LUFS is negative
    assert peak_dbfs < 0  # dBFS is negative for signals below 0dBFS


def test_measure_loudness_silent_audio_raises_error(silent_audio_path: Path) -> None:
    """Test that silent audio raises LoudnessError."""
    with pytest.raises(LoudnessError, match="Silent audio detected"):
        measure_loudness(silent_audio_path)


def test_normalize_loudness_to_target(
    test_audio_path: Path, tmp_path: Path
) -> None:
    """Test that normalize_loudness adjusts to target LUFS."""
    output_path = tmp_path / "normalized.wav"
    target_lufs = -14.0

    # Normalize
    result_lufs, result_peak = normalize_loudness(
        test_audio_path, output_path, target_lufs
    )

    # Verify output file exists
    assert output_path.exists()

    # Verify returned values
    assert isinstance(result_lufs, float)
    assert isinstance(result_peak, float)

    # Target LUFS should be close to requested (within 0.5 LUFS)
    assert abs(result_lufs - target_lufs) < 0.5


def test_normalize_loudness_default_target(
    test_audio_path: Path, tmp_path: Path
) -> None:
    """Test that normalize_loudness uses default target of -14.0 LUFS."""
    output_path = tmp_path / "normalized_default.wav"

    result_lufs, _ = normalize_loudness(test_audio_path, output_path)

    # Default target is -14.0 LUFS
    assert abs(result_lufs - (-14.0)) < 0.5


def test_normalize_loudness_preserves_sample_rate(
    test_audio_path: Path, tmp_path: Path
) -> None:
    """Test that normalize_loudness preserves sample rate."""
    output_path = tmp_path / "normalized_sr.wav"

    # Get original sample rate
    _, original_sr = sf.read(test_audio_path)

    # Normalize
    normalize_loudness(test_audio_path, output_path)

    # Check output sample rate
    _, output_sr = sf.read(output_path)
    assert output_sr == original_sr


def test_normalize_loudness_silent_audio_raises_error(
    silent_audio_path: Path, tmp_path: Path
) -> None:
    """Test that normalizing silent audio raises LoudnessError."""
    output_path = tmp_path / "normalized_silent.wav"

    with pytest.raises(LoudnessError, match="Silent audio detected"):
        normalize_loudness(silent_audio_path, output_path)


def test_normalize_loudness_with_stereo_audio(tmp_path: Path) -> None:
    """Test that normalize_loudness handles stereo audio."""
    # Create stereo test file
    input_path = tmp_path / "stereo.wav"
    output_path = tmp_path / "normalized_stereo.wav"

    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)

    # Generate stereo sine wave
    t = np.linspace(0, duration, samples, endpoint=False)
    left = 0.5 * np.sin(2 * np.pi * 440 * t)
    right = 0.5 * np.sin(2 * np.pi * 550 * t)
    stereo = np.column_stack((left, right))

    sf.write(input_path, stereo, sample_rate)

    # Normalize
    result_lufs, result_peak = normalize_loudness(input_path, output_path)

    # Verify output exists
    assert output_path.exists()
    assert isinstance(result_lufs, float)
    assert isinstance(result_peak, float)


def test_measure_loudness_with_different_levels(tmp_path: Path) -> None:
    """Test that measure_loudness detects different loudness levels."""
    sample_rate = 48000
    duration = 1.0
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)

    # Create quiet audio (amplitude 0.1)
    quiet_path = tmp_path / "quiet.wav"
    quiet_audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    sf.write(quiet_path, quiet_audio, sample_rate)

    # Create loud audio (amplitude 0.8)
    loud_path = tmp_path / "loud.wav"
    loud_audio = 0.8 * np.sin(2 * np.pi * 440 * t)
    sf.write(loud_path, loud_audio, sample_rate)

    # Measure both
    quiet_lufs, quiet_peak = measure_loudness(quiet_path)
    loud_lufs, loud_peak = measure_loudness(loud_path)

    # Loud audio should have higher LUFS (less negative) and peak
    assert loud_lufs > quiet_lufs
    assert loud_peak > quiet_peak
