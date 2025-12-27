"""Tests for volume normalization functions."""

import numpy as np
import pytest

from guitar_tone_shootout.normalize import (
    DEFAULT_INPUT_RMS_DB,
    DEFAULT_OUTPUT_RMS_DB,
    NormalizationError,
    calculate_input_gain,
    calculate_output_gain,
    db_to_linear,
    linear_to_db,
    match_loudness,
    normalize_peak,
    normalize_rms,
    peak_db,
    rms_db,
    rms_linear,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_audio() -> np.ndarray:
    """1 second of 440Hz sine wave at moderate level."""
    t = np.linspace(0, 1, 44100, endpoint=False)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def quiet_audio() -> np.ndarray:
    """Very quiet audio signal."""
    t = np.linspace(0, 1, 44100, endpoint=False)
    return (0.01 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def loud_audio() -> np.ndarray:
    """Loud audio signal near clipping."""
    t = np.linspace(0, 1, 44100, endpoint=False)
    return (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def silent_audio() -> np.ndarray:
    """Completely silent audio."""
    return np.zeros(44100, dtype=np.float32)


# =============================================================================
# Conversion Tests
# =============================================================================


def test_db_to_linear_zero() -> None:
    """0 dB should equal linear 1.0."""
    assert db_to_linear(0) == pytest.approx(1.0)


def test_db_to_linear_minus_6() -> None:
    """-6 dB should be approximately 0.5."""
    assert db_to_linear(-6) == pytest.approx(0.501, rel=0.01)


def test_db_to_linear_plus_6() -> None:
    """+6 dB should be approximately 2.0."""
    assert db_to_linear(6) == pytest.approx(1.995, rel=0.01)


def test_linear_to_db_one() -> None:
    """Linear 1.0 should be 0 dB."""
    assert linear_to_db(1.0) == pytest.approx(0.0)


def test_linear_to_db_half() -> None:
    """Linear 0.5 should be approximately -6 dB."""
    assert linear_to_db(0.5) == pytest.approx(-6.0, abs=0.1)


def test_linear_to_db_zero() -> None:
    """Linear 0 should be negative infinity."""
    result = linear_to_db(0.0)
    assert result == float("-inf")


def test_db_linear_roundtrip() -> None:
    """Convert to linear and back should preserve value."""
    original_db = -12.5
    linear = db_to_linear(original_db)
    back_to_db = linear_to_db(linear)
    assert back_to_db == pytest.approx(original_db)


# =============================================================================
# RMS Measurement Tests
# =============================================================================


def test_rms_linear_sine(sample_audio: np.ndarray) -> None:
    """RMS of 0.3 amplitude sine should be ~0.212."""
    rms = rms_linear(sample_audio)
    # RMS of sine = amplitude / sqrt(2)
    expected = 0.3 / np.sqrt(2)
    assert rms == pytest.approx(expected, rel=0.01)


def test_rms_linear_2d_array() -> None:
    """Should handle 2D arrays."""
    audio_2d = np.array([[0.5, 0.5, 0.5, 0.5]], dtype=np.float32)
    rms = rms_linear(audio_2d)
    assert rms == pytest.approx(0.5)


def test_rms_db_calculation(sample_audio: np.ndarray) -> None:
    """RMS in dB should be reasonable value."""
    db = rms_db(sample_audio)
    # 0.3 amplitude sine -> RMS ~0.212 -> ~-13.5 dB
    assert -20 < db < 0


def test_rms_db_silent_raises(silent_audio: np.ndarray) -> None:
    """Should raise for silent audio."""
    with pytest.raises(NormalizationError, match="Cannot calculate RMS"):
        rms_db(silent_audio)


# =============================================================================
# Peak Measurement Tests
# =============================================================================


def test_peak_db_calculation(sample_audio: np.ndarray) -> None:
    """Peak of 0.3 amplitude should be ~-10.5 dB."""
    peak = peak_db(sample_audio)
    expected = linear_to_db(0.3)
    assert peak == pytest.approx(expected, abs=0.1)


def test_peak_db_silent(silent_audio: np.ndarray) -> None:
    """Peak of silent audio should be negative infinity."""
    assert peak_db(silent_audio) == float("-inf")


def test_peak_db_clipping() -> None:
    """Peak at 1.0 should be 0 dBFS."""
    audio = np.array([1.0, -1.0], dtype=np.float32)
    assert peak_db(audio) == pytest.approx(0.0)


# =============================================================================
# RMS Normalization Tests
# =============================================================================


def test_normalize_rms_target(sample_audio: np.ndarray) -> None:
    """Normalized audio should have target RMS."""
    target = -14.0
    normalized = normalize_rms(sample_audio, target_db=target)

    result_rms = rms_db(normalized)
    assert result_rms == pytest.approx(target, abs=0.5)


def test_normalize_rms_increases_level(quiet_audio: np.ndarray) -> None:
    """Should increase level of quiet audio."""
    original_rms = rms_db(quiet_audio)
    target = -14.0

    normalized = normalize_rms(quiet_audio, target_db=target)
    new_rms = rms_db(normalized)

    assert new_rms > original_rms


def test_normalize_rms_decreases_level(loud_audio: np.ndarray) -> None:
    """Should decrease level of loud audio."""
    original_rms = rms_db(loud_audio)
    target = -20.0

    normalized = normalize_rms(loud_audio, target_db=target)
    new_rms = rms_db(normalized)

    assert new_rms < original_rms


def test_normalize_rms_silent_unchanged(silent_audio: np.ndarray) -> None:
    """Silent audio should be returned unchanged."""
    normalized = normalize_rms(silent_audio)

    np.testing.assert_array_equal(normalized, silent_audio)


def test_normalize_rms_preserves_dtype(sample_audio: np.ndarray) -> None:
    """Output should be float32."""
    normalized = normalize_rms(sample_audio)
    assert normalized.dtype == np.float32


def test_normalize_rms_preserves_shape(sample_audio: np.ndarray) -> None:
    """Output should have same shape as input."""
    normalized = normalize_rms(sample_audio)
    assert normalized.shape == sample_audio.shape


def test_normalize_rms_2d_preserves_shape() -> None:
    """Should preserve 2D shape."""
    audio_2d = np.random.randn(1, 44100).astype(np.float32) * 0.3
    normalized = normalize_rms(audio_2d)
    assert normalized.shape == audio_2d.shape


def test_normalize_rms_peak_limiting() -> None:
    """Should apply limiting if peaks would clip."""
    # Create audio that would clip when normalized
    audio = np.array([0.001] * 1000 + [0.9], dtype=np.float32)

    # Normalize to very high target (would cause clipping)
    normalized = normalize_rms(audio, target_db=-6.0, peak_limit_db=-0.1)

    # Peak should be limited
    assert np.max(np.abs(normalized)) <= db_to_linear(-0.1)


# =============================================================================
# Peak Normalization Tests
# =============================================================================


def test_normalize_peak_target() -> None:
    """Peak-normalized audio should have target peak."""
    audio = np.sin(np.linspace(0, 10, 1000)).astype(np.float32) * 0.5
    target = -3.0

    normalized = normalize_peak(audio, target_db=target)

    result_peak = peak_db(normalized)
    assert result_peak == pytest.approx(target, abs=0.1)


def test_normalize_peak_silent_unchanged(silent_audio: np.ndarray) -> None:
    """Silent audio should be returned unchanged."""
    normalized = normalize_peak(silent_audio)
    np.testing.assert_array_equal(normalized, silent_audio)


# =============================================================================
# Loudness Matching Tests
# =============================================================================


def test_match_loudness_rms(sample_audio: np.ndarray, quiet_audio: np.ndarray) -> None:
    """Matched audio should have same RMS as reference."""
    matched = match_loudness(quiet_audio, sample_audio, method="rms")

    ref_rms = rms_db(sample_audio)
    result_rms = rms_db(matched)

    assert result_rms == pytest.approx(ref_rms, abs=0.5)


def test_match_loudness_peak(sample_audio: np.ndarray, quiet_audio: np.ndarray) -> None:
    """Matched audio should have same peak as reference."""
    matched = match_loudness(quiet_audio, sample_audio, method="peak")

    ref_peak = peak_db(sample_audio)
    result_peak = peak_db(matched)

    assert result_peak == pytest.approx(ref_peak, abs=0.1)


def test_match_loudness_invalid_method(sample_audio: np.ndarray) -> None:
    """Should raise for unknown method."""
    with pytest.raises(NormalizationError, match="Unknown method"):
        match_loudness(sample_audio, sample_audio, method="invalid")


# =============================================================================
# Gain Calculation Tests
# =============================================================================


def test_calculate_input_gain(sample_audio: np.ndarray) -> None:
    """Calculate gain needed for input normalization."""
    gain = calculate_input_gain(sample_audio)

    # Apply the gain and check result
    current_rms = rms_db(sample_audio)
    expected_gain = DEFAULT_INPUT_RMS_DB - current_rms

    assert gain == pytest.approx(expected_gain, abs=0.1)


def test_calculate_output_gain(sample_audio: np.ndarray) -> None:
    """Calculate gain needed for output normalization."""
    gain = calculate_output_gain(sample_audio)

    current_rms = rms_db(sample_audio)
    expected_gain = DEFAULT_OUTPUT_RMS_DB - current_rms

    assert gain == pytest.approx(expected_gain, abs=0.1)


def test_calculate_input_gain_custom_target(sample_audio: np.ndarray) -> None:
    """Calculate gain with custom target."""
    custom_target = -24.0
    gain = calculate_input_gain(sample_audio, target_db=custom_target)

    current_rms = rms_db(sample_audio)
    expected_gain = custom_target - current_rms

    assert gain == pytest.approx(expected_gain, abs=0.1)


# =============================================================================
# Default Values Tests
# =============================================================================


def test_default_input_target() -> None:
    """Default input target should be -18 dB."""
    assert DEFAULT_INPUT_RMS_DB == -18.0


def test_default_output_target() -> None:
    """Default output target should be -14 dB."""
    assert DEFAULT_OUTPUT_RMS_DB == -14.0
