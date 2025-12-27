"""Audio metrics extraction for guitar tone analysis.

This module provides comprehensive audio analysis metrics for comparing
guitar tones in A/B shootouts, including:

- Core Metrics: RMS, Peak, Crest Factor, Dynamic Range
- Spectral Metrics: Spectral Centroid, Bass/Mid/Treble Energy
- Advanced Metrics: LUFS, Transient Density, Attack Time, Sustain Decay Rate

All metrics are returned as Pydantic models for easy JSON serialization
and API integration.

Example:
    >>> from guitar_tone_shootout.metrics import extract_metrics
    >>> from guitar_tone_shootout.audio import load_audio
    >>> audio, sr = load_audio(Path("guitar.wav"))
    >>> metrics = extract_metrics(audio, sr)
    >>> print(metrics.model_dump_json(indent=2))
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Frequency band boundaries (Hz)
BASS_LOW = 20.0
BASS_HIGH = 250.0
MID_LOW = 250.0
MID_HIGH = 2000.0
TREBLE_LOW = 2000.0
TREBLE_HIGH = 20000.0

# Transient detection thresholds
TRANSIENT_THRESHOLD_DB = 6.0  # dB above RMS to consider a transient
TRANSIENT_MIN_INTERVAL_MS = 50.0  # Minimum time between transients

# Attack/sustain analysis parameters
ATTACK_THRESHOLD_RATIO = 0.9  # Percentage of peak to reach
SUSTAIN_WINDOW_MS = 100.0  # Window for measuring decay rate


class CoreMetrics(BaseModel):
    """Core loudness and dynamic metrics.

    Attributes:
        rms_dbfs: RMS level in dB relative to full scale
        peak_dbfs: Peak level in dB relative to full scale
        crest_factor_db: Peak-to-RMS ratio in dB (indicates dynamic range)
        dynamic_range_db: Difference between loudest and quietest parts
    """

    rms_dbfs: float = Field(..., description="RMS level in dBFS")
    peak_dbfs: float = Field(..., description="Peak level in dBFS")
    crest_factor_db: float = Field(..., description="Peak/RMS ratio in dB")
    dynamic_range_db: float = Field(..., description="Dynamic range in dB")


class SpectralMetrics(BaseModel):
    """Spectral distribution metrics.

    Attributes:
        spectral_centroid_hz: Center of mass of the spectrum (brightness indicator)
        bass_energy_ratio: Proportion of energy in bass range (20-250 Hz)
        mid_energy_ratio: Proportion of energy in mid range (250-2000 Hz)
        treble_energy_ratio: Proportion of energy in treble range (2000-20000 Hz)
    """

    spectral_centroid_hz: float = Field(
        ..., description="Spectral centroid in Hz (brightness)"
    )
    bass_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Bass energy (20-250 Hz) ratio"
    )
    mid_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Mid energy (250-2000 Hz) ratio"
    )
    treble_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Treble energy (2000-20000 Hz) ratio"
    )


class AdvancedMetrics(BaseModel):
    """Advanced dynamics and envelope metrics.

    Attributes:
        lufs_integrated: Integrated loudness in LUFS (EBU R128)
        transient_density: Number of transients per second
        attack_time_ms: Time to reach peak amplitude in milliseconds
        sustain_decay_rate_db_s: Rate of amplitude decay in dB/second
    """

    lufs_integrated: float = Field(..., description="Integrated loudness in LUFS")
    transient_density: float = Field(
        ..., ge=0.0, description="Transients per second"
    )
    attack_time_ms: float = Field(
        ..., ge=0.0, description="Attack time in milliseconds"
    )
    sustain_decay_rate_db_s: float = Field(
        ..., description="Sustain decay rate in dB/second"
    )


class AudioMetrics(BaseModel):
    """Complete audio metrics for a guitar tone sample.

    This is the top-level model containing all extracted metrics,
    suitable for JSON serialization and comparison.

    Attributes:
        duration_seconds: Length of the audio in seconds
        sample_rate: Sample rate in Hz
        core: Core loudness metrics
        spectral: Spectral distribution metrics
        advanced: Advanced dynamics metrics
    """

    duration_seconds: float = Field(..., ge=0.0, description="Audio duration in seconds")
    sample_rate: int = Field(..., gt=0, description="Sample rate in Hz")
    core: CoreMetrics = Field(..., description="Core loudness metrics")
    spectral: SpectralMetrics = Field(..., description="Spectral distribution metrics")
    advanced: AdvancedMetrics = Field(..., description="Advanced dynamics metrics")


# =============================================================================
# Core Metrics Functions
# =============================================================================


def calculate_rms_dbfs(audio: NDArray[np.floating]) -> float:
    """Calculate RMS level in dBFS.

    Args:
        audio: Audio samples (1D array)

    Returns:
        RMS level in dB relative to full scale
    """
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    if rms == 0:
        return float("-inf")
    return float(20 * np.log10(rms))


def calculate_peak_dbfs(audio: NDArray[np.floating]) -> float:
    """Calculate peak level in dBFS.

    Args:
        audio: Audio samples (1D array)

    Returns:
        Peak level in dB relative to full scale
    """
    peak = np.max(np.abs(audio))
    if peak == 0:
        return float("-inf")
    return float(20 * np.log10(peak))


def calculate_crest_factor_db(
    audio: NDArray[np.floating],
    rms_dbfs: float | None = None,
    peak_dbfs: float | None = None,
) -> float:
    """Calculate crest factor (peak-to-RMS ratio) in dB.

    The crest factor indicates how "peaky" a signal is. Higher values
    indicate more dynamic range and transient content.

    Args:
        audio: Audio samples (1D array)
        rms_dbfs: Pre-computed RMS in dBFS (optional)
        peak_dbfs: Pre-computed peak in dBFS (optional)

    Returns:
        Crest factor in dB
    """
    if rms_dbfs is None:
        rms_dbfs = calculate_rms_dbfs(audio)
    if peak_dbfs is None:
        peak_dbfs = calculate_peak_dbfs(audio)

    if np.isinf(rms_dbfs):
        return 0.0

    return peak_dbfs - rms_dbfs


def calculate_dynamic_range_db(
    audio: NDArray[np.floating],
    sample_rate: int,
    window_ms: float = 50.0,
) -> float:
    """Calculate dynamic range as difference between loud and quiet parts.

    Uses a sliding window to find the loudest and quietest portions
    of the audio, excluding silence.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz
        window_ms: Analysis window size in milliseconds

    Returns:
        Dynamic range in dB
    """
    window_samples = max(1, int(sample_rate * window_ms / 1000))

    # Calculate RMS in sliding windows
    n_windows = max(1, len(audio) // window_samples)
    rms_values = []

    for i in range(n_windows):
        start = i * window_samples
        end = start + window_samples
        window = audio[start:end]
        rms = np.sqrt(np.mean(window.astype(np.float64) ** 2))
        if rms > 0:  # Exclude silence
            rms_values.append(rms)

    if len(rms_values) < 2:
        return 0.0

    # Use percentiles to be robust against outliers
    loud = np.percentile(rms_values, 95)
    quiet = np.percentile(rms_values, 5)

    if quiet <= 0:
        return 0.0

    return float(20 * np.log10(loud / quiet))


def extract_core_metrics(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> CoreMetrics:
    """Extract all core metrics from audio.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        CoreMetrics model with all core metrics
    """
    rms_dbfs = calculate_rms_dbfs(audio)
    peak_dbfs = calculate_peak_dbfs(audio)
    crest_factor_db = calculate_crest_factor_db(
        audio, rms_dbfs=rms_dbfs, peak_dbfs=peak_dbfs
    )
    dynamic_range_db = calculate_dynamic_range_db(audio, sample_rate)

    return CoreMetrics(
        rms_dbfs=rms_dbfs,
        peak_dbfs=peak_dbfs,
        crest_factor_db=crest_factor_db,
        dynamic_range_db=dynamic_range_db,
    )


# =============================================================================
# Spectral Metrics Functions
# =============================================================================


def calculate_spectral_centroid_hz(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> float:
    """Calculate spectral centroid (center of mass of spectrum).

    The spectral centroid is a measure of the "brightness" of a sound.
    Higher values indicate brighter, more trebly sounds.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        Spectral centroid in Hz
    """
    # Compute FFT
    n = len(audio)
    fft = np.fft.rfft(audio.astype(np.float64))
    magnitude = np.abs(fft)

    # Frequency bins
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

    # Compute centroid as weighted average
    total_magnitude = np.sum(magnitude)
    if total_magnitude == 0:
        return 0.0

    centroid = float(np.sum(freqs * magnitude) / total_magnitude)
    return centroid


def calculate_band_energy_ratios(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> tuple[float, float, float]:
    """Calculate energy ratios for bass, mid, and treble bands.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        Tuple of (bass_ratio, mid_ratio, treble_ratio)
    """
    # Compute FFT
    n = len(audio)
    fft = np.fft.rfft(audio.astype(np.float64))
    power = np.abs(fft) ** 2

    # Frequency bins
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

    # Calculate energy in each band
    bass_mask = (freqs >= BASS_LOW) & (freqs < BASS_HIGH)
    mid_mask = (freqs >= MID_LOW) & (freqs < MID_HIGH)
    treble_mask = (freqs >= TREBLE_LOW) & (freqs <= min(TREBLE_HIGH, sample_rate / 2))

    bass_energy = np.sum(power[bass_mask])
    mid_energy = np.sum(power[mid_mask])
    treble_energy = np.sum(power[treble_mask])

    total_energy = bass_energy + mid_energy + treble_energy

    if total_energy == 0:
        return 0.0, 0.0, 0.0

    return (
        float(bass_energy / total_energy),
        float(mid_energy / total_energy),
        float(treble_energy / total_energy),
    )


def extract_spectral_metrics(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> SpectralMetrics:
    """Extract all spectral metrics from audio.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        SpectralMetrics model with all spectral metrics
    """
    centroid = calculate_spectral_centroid_hz(audio, sample_rate)
    bass, mid, treble = calculate_band_energy_ratios(audio, sample_rate)

    return SpectralMetrics(
        spectral_centroid_hz=centroid,
        bass_energy_ratio=bass,
        mid_energy_ratio=mid,
        treble_energy_ratio=treble,
    )


# =============================================================================
# Advanced Metrics Functions
# =============================================================================


def calculate_lufs_integrated(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> float:
    """Calculate integrated loudness in LUFS (EBU R128 simplified).

    This is a simplified implementation that applies K-weighting and
    gated measurement. For full EBU R128 compliance, use pyloudnorm.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        Integrated loudness in LUFS
    """
    # Try to use pyloudnorm if available (more accurate)
    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sample_rate)
        # pyloudnorm expects 2D array (samples, channels)
        audio_2d = audio.reshape(-1, 1)
        lufs = meter.integrated_loudness(audio_2d)
        return float(lufs) if not np.isnan(lufs) else float("-inf")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"pyloudnorm failed, using simplified LUFS: {e}")

    # Simplified LUFS calculation (K-weighted RMS approximation)
    # Apply simplified K-weighting filter
    audio_weighted = _apply_k_weighting(audio.astype(np.float64), sample_rate)

    # Calculate mean square
    mean_square = np.mean(audio_weighted**2)
    if mean_square <= 0:
        return float("-inf")

    # Simplified approximation: LUFS = -0.691 + 10 * log10(mean_square)
    lufs = -0.691 + 10 * np.log10(mean_square)
    return float(lufs)


def _apply_k_weighting(
    audio: NDArray[np.float64],
    sample_rate: int,
) -> NDArray[np.float64]:
    """Apply simplified K-weighting filter for LUFS measurement.

    K-weighting consists of a high-shelf filter and high-pass filter
    designed to approximate human loudness perception.

    Args:
        audio: Audio samples
        sample_rate: Sample rate in Hz

    Returns:
        K-weighted audio
    """
    try:
        from scipy.signal import iirfilter, sosfilt
    except ImportError:
        # Fallback: return unweighted audio
        logger.debug("scipy not available, using unweighted LUFS")
        return audio

    # Pre-filter (high shelf at 1500 Hz, +4 dB)
    # Simplified: use a gentle high-frequency boost
    sos_shelf = iirfilter(
        2, 1500, btype="high", ftype="butter", fs=sample_rate, output="sos"
    )

    # High-pass filter at 38 Hz
    sos_hp = iirfilter(
        2, 38, btype="high", ftype="butter", fs=sample_rate, output="sos"
    )

    # Apply filters
    filtered = sosfilt(sos_shelf, audio)
    filtered = sosfilt(sos_hp, filtered)

    # Add slight boost for high-shelf approximation
    # K-weighting boosts highs by about 4dB
    from scipy.signal import iirfilter as iir

    sos_boost = iir(
        1, 2000, btype="high", ftype="butter", fs=sample_rate, output="sos"
    )
    boosted = sosfilt(sos_boost, audio) * 0.5  # Gentle boost
    result: NDArray[np.float64] = filtered + boosted * 0.3

    return result


def calculate_transient_density(
    audio: NDArray[np.floating],
    sample_rate: int,
    threshold_db: float = TRANSIENT_THRESHOLD_DB,
    min_interval_ms: float = TRANSIENT_MIN_INTERVAL_MS,
) -> float:
    """Calculate transient density (transients per second).

    Detects transients by finding peaks in the amplitude envelope
    that exceed the RMS by a threshold amount.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz
        threshold_db: dB above RMS to consider a transient
        min_interval_ms: Minimum time between transients in ms

    Returns:
        Number of transients per second
    """
    # Calculate envelope using absolute value with smoothing
    envelope = np.abs(audio.astype(np.float64))

    # Smooth the envelope
    window_size = max(1, int(sample_rate * 0.005))  # 5ms window
    kernel = np.ones(window_size) / window_size
    envelope = np.convolve(envelope, kernel, mode="same")

    # Calculate RMS threshold
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    if rms == 0:
        return 0.0

    threshold_linear = rms * (10 ** (threshold_db / 20))
    min_interval_samples = int(sample_rate * min_interval_ms / 1000)

    # Find peaks above threshold
    above_threshold = envelope > threshold_linear

    # Find rising edges (transient onsets)
    rising_edges = np.diff(above_threshold.astype(int)) == 1
    transient_indices = np.where(rising_edges)[0]

    # Filter by minimum interval
    if len(transient_indices) == 0:
        return 0.0

    filtered_indices = [transient_indices[0]]
    for idx in transient_indices[1:]:
        if idx - filtered_indices[-1] >= min_interval_samples:
            filtered_indices.append(idx)

    # Calculate density
    duration = len(audio) / sample_rate
    if duration == 0:
        return 0.0

    return float(len(filtered_indices) / duration)


def calculate_attack_time_ms(
    audio: NDArray[np.floating],
    sample_rate: int,
    threshold_ratio: float = ATTACK_THRESHOLD_RATIO,
) -> float:
    """Calculate attack time (time to reach peak amplitude).

    Measures the time from when the signal first rises above the noise
    floor to when it reaches its peak amplitude.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz
        threshold_ratio: Ratio of peak to consider "reached" (default 0.9)

    Returns:
        Attack time in milliseconds
    """
    envelope = np.abs(audio.astype(np.float64))
    peak = np.max(envelope)

    if peak == 0:
        return 0.0

    # Find noise floor (first 10ms or 1% of signal, whichever is smaller)
    noise_samples = min(int(sample_rate * 0.01), max(1, len(audio) // 100))
    noise_floor = np.mean(envelope[:noise_samples]) if noise_samples > 0 else 0

    # Threshold for signal start (3x noise floor or 1% of peak)
    start_threshold = max(noise_floor * 3, peak * 0.01)

    # Threshold for signal "reached peak"
    peak_threshold = peak * threshold_ratio

    # Find first sample above start threshold
    above_start = np.where(envelope > start_threshold)[0]
    if len(above_start) == 0:
        return 0.0
    start_idx = above_start[0]

    # Find first sample above peak threshold (after start)
    above_peak = np.where(envelope[start_idx:] > peak_threshold)[0]
    if len(above_peak) == 0:
        # Use the peak location as fallback
        peak_idx = np.argmax(envelope[start_idx:]) + start_idx
    else:
        peak_idx = above_peak[0] + start_idx

    # Calculate time in milliseconds
    attack_samples = peak_idx - start_idx
    attack_time_ms = (attack_samples / sample_rate) * 1000

    return float(attack_time_ms)


def calculate_sustain_decay_rate_db_s(
    audio: NDArray[np.floating],
    sample_rate: int,
    window_ms: float = SUSTAIN_WINDOW_MS,
) -> float:
    """Calculate sustain decay rate in dB per second.

    Measures how quickly the sustained portion of the signal decays.
    This is characteristic of amp compression and sustain.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz
        window_ms: Window size for decay measurement

    Returns:
        Decay rate in dB/second (negative = decaying)
    """
    envelope = np.abs(audio.astype(np.float64))

    # Smooth the envelope
    window_samples = max(1, int(sample_rate * 0.01))  # 10ms smoothing
    kernel = np.ones(window_samples) / window_samples
    envelope = np.convolve(envelope, kernel, mode="same")

    # Find the peak
    peak_idx = np.argmax(envelope)
    peak_value = envelope[peak_idx]

    if peak_value == 0:
        return 0.0

    # Analyze the portion after the peak (sustain/decay region)
    decay_region = envelope[peak_idx:]

    if len(decay_region) < 2:
        return 0.0

    # Use multiple measurement windows to get average decay rate
    measurement_window = max(2, int(sample_rate * window_ms / 1000))

    decay_rates = []
    for i in range(0, len(decay_region) - measurement_window, measurement_window):
        start_amp = np.mean(decay_region[i : i + measurement_window // 2])
        end_amp = np.mean(
            decay_region[i + measurement_window // 2 : i + measurement_window]
        )

        if start_amp > 0 and end_amp > 0:
            # Calculate dB change
            db_change = 20 * np.log10(end_amp / start_amp)
            # Time in seconds for this window
            time_s = (measurement_window / 2) / sample_rate
            if time_s > 0:
                decay_rates.append(db_change / time_s)

    if not decay_rates:
        return 0.0

    # Return median to be robust against outliers
    return float(np.median(decay_rates))


def extract_advanced_metrics(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> AdvancedMetrics:
    """Extract all advanced metrics from audio.

    Args:
        audio: Audio samples (1D array)
        sample_rate: Sample rate in Hz

    Returns:
        AdvancedMetrics model with all advanced metrics
    """
    lufs = calculate_lufs_integrated(audio, sample_rate)
    transient_density = calculate_transient_density(audio, sample_rate)
    attack_time = calculate_attack_time_ms(audio, sample_rate)
    decay_rate = calculate_sustain_decay_rate_db_s(audio, sample_rate)

    return AdvancedMetrics(
        lufs_integrated=lufs,
        transient_density=transient_density,
        attack_time_ms=attack_time,
        sustain_decay_rate_db_s=decay_rate,
    )


# =============================================================================
# Main Extraction Function
# =============================================================================


def extract_metrics(
    audio: NDArray[np.floating],
    sample_rate: int,
) -> AudioMetrics:
    """Extract all audio metrics from an audio signal.

    This is the main entry point for audio analysis. It computes
    all core, spectral, and advanced metrics and returns them
    in a structured Pydantic model.

    Args:
        audio: Audio samples as 1D numpy array
        sample_rate: Sample rate in Hz

    Returns:
        AudioMetrics model containing all extracted metrics

    Example:
        >>> audio, sr = load_audio(Path("guitar.wav"))
        >>> metrics = extract_metrics(audio, sr)
        >>> print(f"RMS: {metrics.core.rms_dbfs:.1f} dBFS")
        >>> print(f"Brightness: {metrics.spectral.spectral_centroid_hz:.0f} Hz")
    """
    # Ensure 1D array
    if audio.ndim > 1:
        audio = audio.flatten()

    duration = len(audio) / sample_rate

    logger.debug(
        f"Extracting metrics: {duration:.2f}s @ {sample_rate} Hz "
        f"({len(audio)} samples)"
    )

    # Extract all metric groups
    core = extract_core_metrics(audio, sample_rate)
    spectral = extract_spectral_metrics(audio, sample_rate)
    advanced = extract_advanced_metrics(audio, sample_rate)

    return AudioMetrics(
        duration_seconds=duration,
        sample_rate=sample_rate,
        core=core,
        spectral=spectral,
        advanced=advanced,
    )


def compare_metrics(
    metrics_a: AudioMetrics,
    metrics_b: AudioMetrics,
) -> dict[str, float]:
    """Compare two sets of audio metrics and return differences.

    Useful for A/B comparisons between different amp/cab combinations.

    Args:
        metrics_a: First set of metrics
        metrics_b: Second set of metrics

    Returns:
        Dictionary of metric differences (A - B)

    Example:
        >>> diff = compare_metrics(tone_a_metrics, tone_b_metrics)
        >>> print(f"Brightness diff: {diff['spectral_centroid_hz']:.0f} Hz")
    """
    return {
        # Core differences
        "rms_dbfs": metrics_a.core.rms_dbfs - metrics_b.core.rms_dbfs,
        "peak_dbfs": metrics_a.core.peak_dbfs - metrics_b.core.peak_dbfs,
        "crest_factor_db": (
            metrics_a.core.crest_factor_db - metrics_b.core.crest_factor_db
        ),
        "dynamic_range_db": (
            metrics_a.core.dynamic_range_db - metrics_b.core.dynamic_range_db
        ),
        # Spectral differences
        "spectral_centroid_hz": (
            metrics_a.spectral.spectral_centroid_hz
            - metrics_b.spectral.spectral_centroid_hz
        ),
        "bass_energy_ratio": (
            metrics_a.spectral.bass_energy_ratio - metrics_b.spectral.bass_energy_ratio
        ),
        "mid_energy_ratio": (
            metrics_a.spectral.mid_energy_ratio - metrics_b.spectral.mid_energy_ratio
        ),
        "treble_energy_ratio": (
            metrics_a.spectral.treble_energy_ratio
            - metrics_b.spectral.treble_energy_ratio
        ),
        # Advanced differences
        "lufs_integrated": (
            metrics_a.advanced.lufs_integrated - metrics_b.advanced.lufs_integrated
        ),
        "transient_density": (
            metrics_a.advanced.transient_density - metrics_b.advanced.transient_density
        ),
        "attack_time_ms": (
            metrics_a.advanced.attack_time_ms - metrics_b.advanced.attack_time_ms
        ),
        "sustain_decay_rate_db_s": (
            metrics_a.advanced.sustain_decay_rate_db_s
            - metrics_b.advanced.sustain_decay_rate_db_s
        ),
    }
