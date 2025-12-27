"""Tests for audio metrics extraction functions."""

from __future__ import annotations

import numpy as np
import pytest

from guitar_tone_shootout.metrics import (
    AdvancedMetrics,
    AudioMetrics,
    CoreMetrics,
    SpectralMetrics,
    calculate_attack_time_ms,
    calculate_band_energy_ratios,
    calculate_crest_factor_db,
    calculate_dynamic_range_db,
    calculate_lufs_integrated,
    calculate_peak_dbfs,
    calculate_rms_dbfs,
    calculate_spectral_centroid_hz,
    calculate_sustain_decay_rate_db_s,
    calculate_transient_density,
    compare_metrics,
    extract_advanced_metrics,
    extract_core_metrics,
    extract_metrics,
    extract_spectral_metrics,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sine_440hz() -> np.ndarray:
    """1 second of 440Hz sine wave at 0.5 amplitude."""
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def sine_1khz() -> np.ndarray:
    """1 second of 1kHz sine wave at 0.5 amplitude."""
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)


@pytest.fixture
def sine_100hz() -> np.ndarray:
    """1 second of 100Hz sine wave at 0.5 amplitude."""
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)


@pytest.fixture
def sine_5khz() -> np.ndarray:
    """1 second of 5kHz sine wave at 0.5 amplitude."""
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 5000 * t)).astype(np.float32)


@pytest.fixture
def impulse() -> np.ndarray:
    """Single sample impulse (maximum crest factor)."""
    audio = np.zeros(44100, dtype=np.float32)
    audio[22050] = 1.0
    return audio


@pytest.fixture
def decaying_sine() -> np.ndarray:
    """Decaying sine wave for attack/sustain testing."""
    sample_rate = 44100
    t = np.linspace(0, 2, sample_rate * 2, endpoint=False)
    # Exponential decay envelope
    envelope = np.exp(-2 * t)
    # 440Hz sine wave
    signal = np.sin(2 * np.pi * 440 * t)
    return (envelope * signal * 0.9).astype(np.float32)


@pytest.fixture
def transient_signal() -> np.ndarray:
    """Signal with clear transients (simulated drum hits)."""
    sample_rate = 44100
    duration = 2  # 2 seconds
    audio = np.zeros(sample_rate * duration, dtype=np.float32)

    # Add 4 transients at 0.25s, 0.75s, 1.25s, 1.75s
    for time_s in [0.25, 0.75, 1.25, 1.75]:
        idx = int(time_s * sample_rate)
        # Create a short burst (50ms decay)
        burst_len = int(0.05 * sample_rate)
        t = np.linspace(0, 0.05, burst_len)
        burst = np.exp(-50 * t) * np.sin(2 * np.pi * 200 * t)
        audio[idx : idx + burst_len] += burst.astype(np.float32) * 0.8

    return audio


@pytest.fixture
def silent_audio() -> np.ndarray:
    """Completely silent audio."""
    return np.zeros(44100, dtype=np.float32)


@pytest.fixture
def noise() -> np.ndarray:
    """White noise at moderate level."""
    np.random.seed(42)  # Reproducible
    return (np.random.randn(44100) * 0.3).astype(np.float32)


# =============================================================================
# Core Metrics Tests
# =============================================================================


class TestRmsDbfs:
    """Tests for calculate_rms_dbfs."""

    def test_sine_wave_rms(self, sine_440hz: np.ndarray) -> None:
        """Sine wave at 0.5 amplitude should be about -6 to -9 dBFS RMS."""
        rms = calculate_rms_dbfs(sine_440hz)
        # RMS of sine is peak / sqrt(2), so 0.5 / sqrt(2) ~= 0.354
        # 20 * log10(0.354) ~= -9.03 dB
        assert -10 < rms < -8

    def test_silent_audio_returns_neg_inf(self, silent_audio: np.ndarray) -> None:
        """Silent audio should return -inf."""
        rms = calculate_rms_dbfs(silent_audio)
        assert rms == float("-inf")

    def test_full_scale_sine(self) -> None:
        """Full scale sine wave should be about -3 dBFS RMS."""
        t = np.linspace(0, 1, 44100, endpoint=False)
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        rms = calculate_rms_dbfs(audio)
        # 1.0 / sqrt(2) ~= 0.707, 20 * log10(0.707) ~= -3.01
        assert -4 < rms < -2


class TestPeakDbfs:
    """Tests for calculate_peak_dbfs."""

    def test_half_amplitude_sine(self, sine_440hz: np.ndarray) -> None:
        """Sine wave at 0.5 amplitude should be -6 dBFS peak."""
        peak = calculate_peak_dbfs(sine_440hz)
        # 20 * log10(0.5) = -6.02 dB
        assert abs(peak - (-6.02)) < 0.1

    def test_full_scale(self) -> None:
        """Full scale should be 0 dBFS."""
        audio = np.array([1.0, -1.0, 0.5], dtype=np.float32)
        peak = calculate_peak_dbfs(audio)
        assert abs(peak) < 0.01

    def test_silent_audio_returns_neg_inf(self, silent_audio: np.ndarray) -> None:
        """Silent audio should return -inf."""
        peak = calculate_peak_dbfs(silent_audio)
        assert peak == float("-inf")


class TestCrestFactor:
    """Tests for calculate_crest_factor_db."""

    def test_sine_wave_crest_factor(self, sine_440hz: np.ndarray) -> None:
        """Sine wave has crest factor of sqrt(2) = 3.01 dB."""
        crest = calculate_crest_factor_db(sine_440hz)
        # Crest factor of sine = peak/RMS = sqrt(2) ~= 3.01 dB
        assert abs(crest - 3.01) < 0.5

    def test_impulse_high_crest_factor(self, impulse: np.ndarray) -> None:
        """Impulse should have very high crest factor."""
        crest = calculate_crest_factor_db(impulse)
        # Impulse has extreme peak-to-RMS ratio
        assert crest > 20


class TestDynamicRange:
    """Tests for calculate_dynamic_range_db."""

    def test_constant_amplitude_low_dynamic_range(
        self, sine_440hz: np.ndarray
    ) -> None:
        """Constant amplitude signal should have low dynamic range."""
        dr = calculate_dynamic_range_db(sine_440hz, 44100)
        # Constant amplitude, should be near 0
        assert dr < 3

    def test_varying_amplitude_higher_dynamic_range(self) -> None:
        """Signal with varying amplitude should show dynamic range."""
        # Create signal with loud and quiet parts
        loud = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)) * 0.9
        quiet = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)) * 0.1
        audio = np.concatenate([loud, quiet]).astype(np.float32)

        dr = calculate_dynamic_range_db(audio, 44100)
        # 20 * log10(0.9/0.1) ~= 19 dB, but with windowing expect less
        assert dr > 10


class TestExtractCoreMetrics:
    """Tests for extract_core_metrics."""

    def test_returns_core_metrics_model(self, sine_440hz: np.ndarray) -> None:
        """Should return a CoreMetrics model."""
        metrics = extract_core_metrics(sine_440hz, 44100)
        assert isinstance(metrics, CoreMetrics)

    def test_all_fields_populated(self, sine_440hz: np.ndarray) -> None:
        """All fields should be populated with finite values."""
        metrics = extract_core_metrics(sine_440hz, 44100)
        assert np.isfinite(metrics.rms_dbfs)
        assert np.isfinite(metrics.peak_dbfs)
        assert np.isfinite(metrics.crest_factor_db)
        assert np.isfinite(metrics.dynamic_range_db)


# =============================================================================
# Spectral Metrics Tests
# =============================================================================


class TestSpectralCentroid:
    """Tests for calculate_spectral_centroid_hz."""

    def test_low_frequency_low_centroid(self, sine_100hz: np.ndarray) -> None:
        """100Hz sine should have centroid near 100Hz."""
        centroid = calculate_spectral_centroid_hz(sine_100hz, 44100)
        assert 50 < centroid < 200

    def test_high_frequency_high_centroid(self, sine_5khz: np.ndarray) -> None:
        """5kHz sine should have centroid near 5kHz."""
        centroid = calculate_spectral_centroid_hz(sine_5khz, 44100)
        assert 4000 < centroid < 6000

    def test_higher_freq_brighter(
        self, sine_440hz: np.ndarray, sine_5khz: np.ndarray
    ) -> None:
        """Higher frequency should have higher centroid."""
        centroid_low = calculate_spectral_centroid_hz(sine_440hz, 44100)
        centroid_high = calculate_spectral_centroid_hz(sine_5khz, 44100)
        assert centroid_high > centroid_low

    def test_silent_audio_zero_centroid(self, silent_audio: np.ndarray) -> None:
        """Silent audio should have zero centroid."""
        centroid = calculate_spectral_centroid_hz(silent_audio, 44100)
        assert centroid == 0.0


class TestBandEnergyRatios:
    """Tests for calculate_band_energy_ratios."""

    def test_bass_frequency_high_bass_ratio(self, sine_100hz: np.ndarray) -> None:
        """100Hz sine should have high bass ratio."""
        bass, mid, treble = calculate_band_energy_ratios(sine_100hz, 44100)
        assert bass > 0.8  # Most energy in bass
        assert mid < 0.2
        assert treble < 0.1

    def test_mid_frequency_high_mid_ratio(self, sine_1khz: np.ndarray) -> None:
        """1kHz sine should have high mid ratio."""
        bass, mid, treble = calculate_band_energy_ratios(sine_1khz, 44100)
        assert mid > 0.8  # Most energy in mid
        assert bass < 0.2
        assert treble < 0.2

    def test_treble_frequency_high_treble_ratio(self, sine_5khz: np.ndarray) -> None:
        """5kHz sine should have high treble ratio."""
        bass, mid, treble = calculate_band_energy_ratios(sine_5khz, 44100)
        assert treble > 0.8  # Most energy in treble
        assert bass < 0.1
        assert mid < 0.2

    def test_ratios_sum_to_one(self, noise: np.ndarray) -> None:
        """Band ratios should sum to approximately 1."""
        bass, mid, treble = calculate_band_energy_ratios(noise, 44100)
        total = bass + mid + treble
        assert abs(total - 1.0) < 0.01


class TestExtractSpectralMetrics:
    """Tests for extract_spectral_metrics."""

    def test_returns_spectral_metrics_model(self, sine_440hz: np.ndarray) -> None:
        """Should return a SpectralMetrics model."""
        metrics = extract_spectral_metrics(sine_440hz, 44100)
        assert isinstance(metrics, SpectralMetrics)

    def test_all_fields_valid(self, sine_440hz: np.ndarray) -> None:
        """All fields should be within valid ranges."""
        metrics = extract_spectral_metrics(sine_440hz, 44100)
        assert metrics.spectral_centroid_hz >= 0
        assert 0 <= metrics.bass_energy_ratio <= 1
        assert 0 <= metrics.mid_energy_ratio <= 1
        assert 0 <= metrics.treble_energy_ratio <= 1


# =============================================================================
# Advanced Metrics Tests
# =============================================================================


class TestLufsIntegrated:
    """Tests for calculate_lufs_integrated."""

    def test_quieter_audio_lower_lufs(self) -> None:
        """Quieter audio should have lower LUFS."""
        t = np.linspace(0, 1, 44100, endpoint=False)
        loud = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.8
        quiet = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.1

        lufs_loud = calculate_lufs_integrated(loud, 44100)
        lufs_quiet = calculate_lufs_integrated(quiet, 44100)

        assert lufs_loud > lufs_quiet

    def test_silent_audio_neg_inf(self, silent_audio: np.ndarray) -> None:
        """Silent audio should return -inf LUFS."""
        lufs = calculate_lufs_integrated(silent_audio, 44100)
        assert lufs == float("-inf")

    def test_reasonable_range(self, sine_440hz: np.ndarray) -> None:
        """LUFS should be in a reasonable range for typical audio."""
        lufs = calculate_lufs_integrated(sine_440hz, 44100)
        # Typical music is -14 to -24 LUFS
        assert -40 < lufs < 0


class TestTransientDensity:
    """Tests for calculate_transient_density."""

    def test_transient_signal_detects_transients(
        self, transient_signal: np.ndarray
    ) -> None:
        """Should detect transients in signal with clear transients."""
        density = calculate_transient_density(transient_signal, 44100)
        # We created 4 transients over 2 seconds = 2 per second
        assert 1.0 < density < 4.0

    def test_constant_sine_low_density(self, sine_440hz: np.ndarray) -> None:
        """Constant sine wave should have low transient density."""
        density = calculate_transient_density(sine_440hz, 44100)
        # Steady sine has minimal transients
        assert density < 2

    def test_silent_audio_zero_density(self, silent_audio: np.ndarray) -> None:
        """Silent audio should have zero transient density."""
        density = calculate_transient_density(silent_audio, 44100)
        assert density == 0.0


class TestAttackTime:
    """Tests for calculate_attack_time_ms."""

    def test_instant_onset_fast_attack(self, sine_440hz: np.ndarray) -> None:
        """Sine wave starting at full amplitude should have fast attack."""
        attack = calculate_attack_time_ms(sine_440hz, 44100)
        # Sine starts immediately, so attack should be very short
        assert attack < 10  # Less than 10ms

    def test_decaying_sine_measures_attack(self, decaying_sine: np.ndarray) -> None:
        """Decaying sine starting at peak should have fast attack."""
        attack = calculate_attack_time_ms(decaying_sine, 44100)
        # Starts at peak, so attack should be nearly instant
        assert attack < 50

    def test_silent_audio_zero_attack(self, silent_audio: np.ndarray) -> None:
        """Silent audio should have zero attack time."""
        attack = calculate_attack_time_ms(silent_audio, 44100)
        assert attack == 0.0


class TestSustainDecayRate:
    """Tests for calculate_sustain_decay_rate_db_s."""

    def test_decaying_signal_negative_rate(self, decaying_sine: np.ndarray) -> None:
        """Decaying signal should have negative decay rate."""
        decay_rate = calculate_sustain_decay_rate_db_s(decaying_sine, 44100)
        # Exponential decay should give negative rate
        assert decay_rate < 0

    def test_constant_amplitude_near_zero_rate(self, sine_440hz: np.ndarray) -> None:
        """Constant amplitude should have decay rate near zero."""
        decay_rate = calculate_sustain_decay_rate_db_s(sine_440hz, 44100)
        # Steady signal, decay rate should be minimal
        assert abs(decay_rate) < 5  # Within 5 dB/s of zero


class TestExtractAdvancedMetrics:
    """Tests for extract_advanced_metrics."""

    def test_returns_advanced_metrics_model(self, sine_440hz: np.ndarray) -> None:
        """Should return an AdvancedMetrics model."""
        metrics = extract_advanced_metrics(sine_440hz, 44100)
        assert isinstance(metrics, AdvancedMetrics)

    def test_all_fields_valid(self, sine_440hz: np.ndarray) -> None:
        """All fields should be valid numbers."""
        metrics = extract_advanced_metrics(sine_440hz, 44100)
        assert np.isfinite(metrics.lufs_integrated)
        assert metrics.transient_density >= 0
        assert metrics.attack_time_ms >= 0
        assert np.isfinite(metrics.sustain_decay_rate_db_s)


# =============================================================================
# Integration Tests
# =============================================================================


class TestExtractMetrics:
    """Tests for extract_metrics main function."""

    def test_returns_audio_metrics_model(self, sine_440hz: np.ndarray) -> None:
        """Should return complete AudioMetrics model."""
        metrics = extract_metrics(sine_440hz, 44100)
        assert isinstance(metrics, AudioMetrics)

    def test_duration_correct(self, sine_440hz: np.ndarray) -> None:
        """Duration should match audio length."""
        metrics = extract_metrics(sine_440hz, 44100)
        assert abs(metrics.duration_seconds - 1.0) < 0.01

    def test_sample_rate_correct(self, sine_440hz: np.ndarray) -> None:
        """Sample rate should be preserved."""
        metrics = extract_metrics(sine_440hz, 44100)
        assert metrics.sample_rate == 44100

    def test_all_sub_models_present(self, sine_440hz: np.ndarray) -> None:
        """All sub-models should be present."""
        metrics = extract_metrics(sine_440hz, 44100)
        assert isinstance(metrics.core, CoreMetrics)
        assert isinstance(metrics.spectral, SpectralMetrics)
        assert isinstance(metrics.advanced, AdvancedMetrics)

    def test_json_serialization(self, sine_440hz: np.ndarray) -> None:
        """Should be JSON serializable."""
        metrics = extract_metrics(sine_440hz, 44100)
        json_str = metrics.model_dump_json()
        assert isinstance(json_str, str)
        assert "rms_dbfs" in json_str
        assert "spectral_centroid_hz" in json_str
        assert "lufs_integrated" in json_str

    def test_2d_array_handled(self) -> None:
        """Should handle 2D arrays by flattening."""
        audio = np.random.randn(2, 22050).astype(np.float32) * 0.3
        metrics = extract_metrics(audio, 44100)
        assert isinstance(metrics, AudioMetrics)
        # Duration should reflect flattened length
        assert metrics.duration_seconds == pytest.approx(1.0, rel=0.01)


class TestCompareMetrics:
    """Tests for compare_metrics function."""

    def test_same_audio_zero_difference(self, sine_440hz: np.ndarray) -> None:
        """Same audio should have zero difference."""
        metrics = extract_metrics(sine_440hz, 44100)
        diff = compare_metrics(metrics, metrics)

        for key, value in diff.items():
            assert abs(value) < 0.01, f"{key} should be near zero"

    def test_different_audio_shows_differences(
        self, sine_100hz: np.ndarray, sine_5khz: np.ndarray
    ) -> None:
        """Different audio should show non-zero differences."""
        metrics_bass = extract_metrics(sine_100hz, 44100)
        metrics_treble = extract_metrics(sine_5khz, 44100)

        diff = compare_metrics(metrics_bass, metrics_treble)

        # Spectral centroid should differ significantly
        assert abs(diff["spectral_centroid_hz"]) > 1000

        # Bass vs treble energy should differ
        assert diff["bass_energy_ratio"] > 0  # Bass has more bass
        assert diff["treble_energy_ratio"] < 0  # Bass has less treble

    def test_returns_all_metrics(self, sine_440hz: np.ndarray) -> None:
        """Should return all expected metric differences."""
        metrics = extract_metrics(sine_440hz, 44100)
        diff = compare_metrics(metrics, metrics)

        expected_keys = {
            "rms_dbfs",
            "peak_dbfs",
            "crest_factor_db",
            "dynamic_range_db",
            "spectral_centroid_hz",
            "bass_energy_ratio",
            "mid_energy_ratio",
            "treble_energy_ratio",
            "lufs_integrated",
            "transient_density",
            "attack_time_ms",
            "sustain_decay_rate_db_s",
        }

        assert set(diff.keys()) == expected_keys


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_short_audio(self) -> None:
        """Should handle very short audio."""
        audio = np.array([0.5, -0.5, 0.5], dtype=np.float32)
        metrics = extract_metrics(audio, 44100)
        assert isinstance(metrics, AudioMetrics)

    def test_different_sample_rates(self) -> None:
        """Should work with different sample rates."""
        t = np.linspace(0, 1, 48000, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

        metrics = extract_metrics(audio, 48000)
        assert metrics.sample_rate == 48000
        assert metrics.duration_seconds == pytest.approx(1.0, rel=0.01)

    def test_clipped_audio(self) -> None:
        """Should handle clipped audio."""
        t = np.linspace(0, 1, 44100, endpoint=False)
        audio = np.clip(np.sin(2 * np.pi * 440 * t) * 2, -1, 1).astype(np.float32)

        metrics = extract_metrics(audio, 44100)
        # Peak should be at 0 dBFS
        assert abs(metrics.core.peak_dbfs) < 0.1

    def test_dc_offset_audio(self) -> None:
        """Should handle audio with DC offset."""
        t = np.linspace(0, 1, 44100, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3 + 0.2).astype(np.float32)

        metrics = extract_metrics(audio, 44100)
        assert isinstance(metrics, AudioMetrics)
        # Should still get valid metrics
        assert np.isfinite(metrics.core.rms_dbfs)
