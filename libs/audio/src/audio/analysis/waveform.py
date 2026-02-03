"""Waveform extraction for audio visualization.

This module provides functions for extracting waveform visualization data
from audio files using numpy for peak calculation.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

from core.domain.value_objects.waveform_data import WaveformData  # type: ignore[import-untyped]


def extract_waveform(
    audio_path: Path,
    *,
    num_peaks: int = 200,
) -> WaveformData:
    """Extract waveform visualization data from audio.

    Args:
        audio_path: Path to the audio file
        num_peaks: Number of peak values to extract (default 200)

    Returns:
        WaveformData for visualization

    Raises:
        FileNotFoundError: If audio file does not exist
        RuntimeError: If audio file cannot be read
    """
    # Validate file exists
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load audio file
    try:
        audio, sample_rate = sf.read(str(audio_path))
    except Exception as e:
        raise RuntimeError(f"Failed to read audio file: {e}") from e

    # Convert stereo to mono if needed
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Calculate samples per peak
    total_samples = len(audio)
    samples_per_peak = max(1, total_samples // num_peaks)

    # Extract peaks by downsampling
    peaks = []
    for i in range(num_peaks):
        start_idx = i * samples_per_peak
        end_idx = min(start_idx + samples_per_peak, total_samples)

        if start_idx >= total_samples:
            break

        # Get max absolute value in this segment
        segment = audio[start_idx:end_idx]
        if len(segment) > 0:
            peak = np.max(np.abs(segment))
            # Preserve sign of the loudest sample
            max_idx = np.argmax(np.abs(segment))
            peaks.append(float(segment[max_idx]) if peak > 0 else 0.0)

    # Calculate duration
    duration = float(total_samples) / sample_rate

    return WaveformData(
        peaks=tuple(peaks),
        sample_rate=int(sample_rate),
        duration_seconds=duration,
        samples_per_peak=samples_per_peak,
    )
