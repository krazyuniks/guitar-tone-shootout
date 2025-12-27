"""Volume normalization utilities for consistent audio levels.

This module provides RMS-based normalization to ensure consistent output
levels across different signal chains in A/B comparisons.

Target Levels:
    - Input normalization: -18 dB RMS (headroom for amp simulation)
    - Output normalization: -14 dB RMS (comfortable listening level)

Future:
    - LUFS normalization for broadcast-standard loudness (EBU R128)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Default target levels
DEFAULT_INPUT_RMS_DB = -18.0  # Headroom for amp simulation
DEFAULT_OUTPUT_RMS_DB = -14.0  # Comfortable output level


class NormalizationError(Exception):
    """Error during audio normalization."""


def rms_db(audio: NDArray[np.float32]) -> float:
    """
    Calculate RMS level in decibels.

    Args:
        audio: Audio data as numpy array (1D or 2D)

    Returns:
        RMS level in dB (relative to full scale)

    Raises:
        NormalizationError: If audio is silent (RMS = 0)
    """
    # Flatten to 1D if needed
    if audio.ndim > 1:
        audio = audio.flatten()

    # Calculate RMS
    rms = np.sqrt(np.mean(audio**2))

    if rms == 0:
        raise NormalizationError("Cannot calculate RMS of silent audio")

    # Convert to dB (0 dBFS = 1.0 amplitude)
    return float(20 * np.log10(rms))


def rms_linear(audio: NDArray[np.float32]) -> float:
    """
    Calculate RMS level as linear amplitude.

    Args:
        audio: Audio data as numpy array

    Returns:
        RMS amplitude (0.0 to ~1.0 for normalized audio)
    """
    if audio.ndim > 1:
        audio = audio.flatten()
    return float(np.sqrt(np.mean(audio**2)))


def peak_db(audio: NDArray[np.float32]) -> float:
    """
    Calculate peak level in decibels.

    Args:
        audio: Audio data as numpy array

    Returns:
        Peak level in dB (relative to full scale)
    """
    if audio.ndim > 1:
        audio = audio.flatten()

    peak = np.max(np.abs(audio))
    if peak == 0:
        return float("-inf")

    return float(20 * np.log10(peak))


def db_to_linear(db: float) -> float:
    """Convert decibels to linear amplitude ratio."""
    return float(10 ** (db / 20))


def linear_to_db(linear: float) -> float:
    """Convert linear amplitude ratio to decibels."""
    if linear <= 0:
        return float("-inf")
    return float(20 * np.log10(linear))


def normalize_rms(
    audio: NDArray[np.float32],
    target_db: float = DEFAULT_OUTPUT_RMS_DB,
    peak_limit_db: float = -0.1,
) -> NDArray[np.float32]:
    """
    Normalize audio to a target RMS level with peak limiting.

    This applies gain to bring the RMS to the target level, then
    applies soft limiting if the peaks would exceed the limit.

    Args:
        audio: Input audio as numpy array (1D or 2D)
        target_db: Target RMS level in dB (default: -14 dB)
        peak_limit_db: Maximum peak level in dB (default: -0.1 dB)

    Returns:
        Normalized audio as numpy array (same shape as input)

    Example:
        >>> audio = load_audio("input.wav")
        >>> normalized = normalize_rms(audio, target_db=-14.0)
        >>> print(f"RMS: {rms_db(normalized):.1f} dB")
        RMS: -14.0 dB
    """
    original_shape = audio.shape
    original_ndim = audio.ndim

    # Work with 1D
    audio_1d = audio.flatten() if audio.ndim > 1 else audio.copy()

    # Check for silence
    current_rms = rms_linear(audio_1d)
    if current_rms == 0:
        logger.warning("Cannot normalize silent audio, returning unchanged")
        return audio.copy()

    # Calculate required gain
    current_db = linear_to_db(current_rms)
    gain_db = target_db - current_db
    gain_linear = db_to_linear(gain_db)

    logger.debug(
        f"Normalizing: {current_db:.1f} dB -> {target_db:.1f} dB (gain: {gain_db:+.1f} dB)"
    )

    # Apply gain
    normalized = audio_1d * gain_linear

    # Check for clipping and apply limiting if needed
    peak = np.max(np.abs(normalized))
    peak_limit = db_to_linear(peak_limit_db)

    if peak > peak_limit:
        # Apply soft limiting (simple compression above threshold)
        reduction_db = linear_to_db(peak) - peak_limit_db
        logger.debug(f"Peak limiting: reducing by {reduction_db:.1f} dB")

        # Simple limiter: scale down to meet peak limit
        normalized = normalized * (peak_limit / peak)

    # Restore original shape
    if original_ndim > 1:
        normalized = normalized.reshape(original_shape)

    return normalized.astype(np.float32)


def normalize_peak(
    audio: NDArray[np.float32],
    target_db: float = -1.0,
) -> NDArray[np.float32]:
    """
    Normalize audio to a target peak level.

    This is simpler than RMS normalization but doesn't account for
    perceived loudness.

    Args:
        audio: Input audio as numpy array
        target_db: Target peak level in dB (default: -1 dB)

    Returns:
        Peak-normalized audio
    """
    original_shape = audio.shape

    audio_1d = audio.flatten() if audio.ndim > 1 else audio.copy()

    current_peak = np.max(np.abs(audio_1d))
    if current_peak == 0:
        logger.warning("Cannot normalize silent audio, returning unchanged")
        return audio.copy()

    target_peak = db_to_linear(target_db)
    gain = target_peak / current_peak

    normalized = audio_1d * gain

    if audio.ndim > 1:
        normalized = normalized.reshape(original_shape)

    result: NDArray[np.float32] = normalized.astype(np.float32)
    return result


def match_loudness(
    audio: NDArray[np.float32],
    reference: NDArray[np.float32],
    method: str = "rms",
) -> NDArray[np.float32]:
    """
    Match the loudness of audio to a reference signal.

    Useful for A/B comparisons where you want both signals at the
    same perceived loudness.

    Args:
        audio: Audio to adjust
        reference: Reference audio to match
        method: "rms" (default) or "peak"

    Returns:
        Audio adjusted to match reference loudness
    """
    if method == "rms":
        ref_level = rms_db(reference)
        return normalize_rms(audio, target_db=ref_level)
    elif method == "peak":
        ref_level = peak_db(reference)
        return normalize_peak(audio, target_db=ref_level)
    else:
        raise NormalizationError(f"Unknown method: {method}")


def calculate_input_gain(
    audio: NDArray[np.float32],
    target_db: float = DEFAULT_INPUT_RMS_DB,
) -> float:
    """
    Calculate the gain needed to bring audio to target input level.

    Use this to determine the input gain for a signal chain without
    actually modifying the audio.

    Args:
        audio: Input audio
        target_db: Target RMS level

    Returns:
        Gain in dB needed to reach target
    """
    current = rms_db(audio)
    return target_db - current


def calculate_output_gain(
    audio: NDArray[np.float32],
    target_db: float = DEFAULT_OUTPUT_RMS_DB,
) -> float:
    """
    Calculate the gain needed for output normalization.

    Use this after processing to determine makeup gain.

    Args:
        audio: Processed audio
        target_db: Target RMS level

    Returns:
        Gain in dB needed to reach target
    """
    current = rms_db(audio)
    return target_db - current
