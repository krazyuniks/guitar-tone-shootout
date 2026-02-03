"""Loudness normalization using EBU R128 standard.

This module provides functions for measuring and normalizing audio loudness
using the pyloudnorm library which implements the EBU R128 standard.
"""

from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf


class LoudnessError(Exception):
    """Exception raised when loudness measurement or normalization fails."""

    pass


def measure_loudness(audio_path: Path) -> tuple[float, float]:
    """Measure audio loudness using EBU R128.

    Args:
        audio_path: Path to the audio file

    Returns:
        Tuple of (integrated_lufs, peak_dbfs)

    Raises:
        LoudnessError: If audio is silent or measurement fails
    """
    # Load audio file
    audio, sample_rate = sf.read(audio_path)

    # Convert stereo to mono if needed
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Check for silent audio
    peak = np.max(np.abs(audio))
    if peak < 1e-6:  # Effectively silent
        raise LoudnessError("Silent audio detected - cannot measure loudness")

    # Measure integrated loudness using pyloudnorm
    meter = pyln.Meter(sample_rate)
    lufs = meter.integrated_loudness(audio)

    # Calculate peak level in dBFS
    peak_dbfs = 20 * np.log10(peak) if peak > 0 else -np.inf

    return (float(lufs), float(peak_dbfs))


def normalize_loudness(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -14.0,
) -> tuple[float, float]:
    """Normalize audio to target loudness.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        target_lufs: Target loudness in LUFS (default: -14.0)

    Returns:
        Tuple of (result_lufs, result_peak_dbfs) after normalization

    Raises:
        LoudnessError: If audio is silent or normalization fails
    """
    # Load audio file
    audio, sample_rate = sf.read(input_path)

    # Convert stereo to mono if needed
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Check for silent audio
    peak = np.max(np.abs(audio))
    if peak < 1e-6:  # Effectively silent
        raise LoudnessError("Silent audio detected - cannot normalize")

    # Measure current loudness
    meter = pyln.Meter(sample_rate)
    current_lufs = meter.integrated_loudness(audio)

    # Normalize to target LUFS
    normalized_audio = pyln.normalize.loudness(audio, current_lufs, target_lufs)

    # Write output file
    sf.write(output_path, normalized_audio, sample_rate)

    # Calculate output metrics
    normalized_peak = np.max(np.abs(normalized_audio))
    peak_dbfs = 20 * np.log10(normalized_peak) if normalized_peak > 0 else -np.inf

    # Measure output loudness to verify
    result_lufs = meter.integrated_loudness(normalized_audio)

    return (float(result_lufs), float(peak_dbfs))
