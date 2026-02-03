"""Pedalboard-based audio processor implementation.

This module implements the AudioProcessor protocol using Pedalboard
for audio processing and PyLoudnorm for loudness measurement.
"""

import time
from pathlib import Path
from typing import ClassVar

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
import torch
from pedalboard import HighpassFilter, Pedalboard  # type: ignore[attr-defined]
from scipy import signal

from core.domain.value_objects.audio_result import AudioResult
from core.domain.value_objects.tone_config import ToneConfig
from core.domain.value_objects.waveform_data import WaveformData

from .ir_loader import load_ir
from .nam_loader import load_nam_model


class ProcessingError(Exception):
    """Exception raised when audio processing fails."""

    pass


class PedalboardAudioProcessor:
    """Audio processor implementation using Pedalboard and PyLoudnorm.

    This class implements the AudioProcessor protocol defined in libs/core/ports/
    using the Pedalboard library for effects processing and PyLoudnorm for
    loudness measurement.

    All methods are async to support potential future async operations
    (e.g., GPU processing, distributed processing).
    """

    # Supported audio formats
    _SUPPORTED_FORMATS: ClassVar[list[str]] = ["wav", "flac", "ogg", "mp3"]

    def __init__(self) -> None:
        """Initialize the processor."""
        pass

    def get_supported_formats(self) -> list[str]:
        """Get list of supported audio formats.

        Returns:
            List of format extensions (e.g., ['wav', 'flac', 'mp3'])
        """
        return self._SUPPORTED_FORMATS.copy()

    def is_format_supported(self, format_ext: str) -> bool:
        """Check if a format is supported.

        Args:
            format_ext: Format extension (without dot)

        Returns:
            True if supported, False otherwise
        """
        return format_ext.lower() in self._SUPPORTED_FORMATS

    async def extract_waveform(
        self,
        audio_path: Path,
        *,
        num_peaks: int = 200,
    ) -> WaveformData:
        """Extract waveform visualization data from audio.

        Args:
            audio_path: Path to the audio file
            num_peaks: Number of peak values to extract

        Returns:
            WaveformData for visualization
        """
        # Load audio file
        audio, sample_rate = sf.read(audio_path)

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
            sample_rate=sample_rate,
            duration_seconds=duration,
            samples_per_peak=samples_per_peak,
        )

    async def measure_loudness(
        self,
        audio_path: Path,
    ) -> tuple[float, float]:
        """Measure audio loudness.

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple of (integrated_lufs, peak_dbfs)
        """
        # Load audio file
        audio, sample_rate = sf.read(audio_path)

        # Convert stereo to mono if needed
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)

        # Measure integrated loudness using pyloudnorm
        meter = pyln.Meter(sample_rate)
        lufs = meter.integrated_loudness(audio)

        # Calculate peak level in dBFS
        peak = np.max(np.abs(audio))
        peak_dbfs = 20 * np.log10(peak) if peak > 0 else -np.inf

        return (float(lufs), float(peak_dbfs))

    async def normalize_loudness(
        self,
        input_path: Path,
        output_path: Path,
        target_lufs: float = -14.0,
    ) -> AudioResult:
        """Normalize audio to target loudness.

        Args:
            input_path: Path to input audio file
            output_path: Path for output file
            target_lufs: Target loudness in LUFS

        Returns:
            AudioResult with processing metadata
        """
        start_time = time.time()

        # Load audio file
        audio, sample_rate = sf.read(input_path)

        # Convert stereo to mono if needed
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)

        # Measure current loudness
        meter = pyln.Meter(sample_rate)
        current_lufs = meter.integrated_loudness(audio)

        # Normalize to target LUFS
        normalized_audio = pyln.normalize.loudness(audio, current_lufs, target_lufs)

        # Write output file
        sf.write(output_path, normalized_audio, sample_rate)

        # Calculate output metrics
        duration = float(len(normalized_audio)) / sample_rate
        peak = np.max(np.abs(normalized_audio))
        peak_dbfs = 20 * np.log10(peak) if peak > 0 else -np.inf

        processing_time = time.time() - start_time

        return AudioResult.create(
            output_path=output_path,
            duration_seconds=duration,
            sample_rate=sample_rate,
            peak_dbfs=float(peak_dbfs),
            lufs_integrated=target_lufs,
            processing_time_seconds=processing_time,
        )

    async def process_di_track(
        self,
        input_path: Path,
        output_path: Path,
        config: ToneConfig,
    ) -> AudioResult:
        """Process a DI track through a tone configuration.

        Args:
            input_path: Path to the input DI audio file
            output_path: Path for the processed output file
            config: Tone processing configuration

        Returns:
            AudioResult with processing metadata

        Raises:
            ProcessingError: If processing fails
        """
        start_time = time.time()

        try:
            # Load audio file
            audio, sample_rate = sf.read(input_path)

            # Convert stereo to mono if needed
            if audio.ndim == 2:
                audio = np.mean(audio, axis=1)

            # Resample if needed
            if sample_rate != config.sample_rate:
                num_samples = int(len(audio) * config.sample_rate / sample_rate)
                audio = signal.resample(audio, num_samples)
                sample_rate = config.sample_rate

            # Build effects chain
            effects = []

            # Add highpass filter if configured
            if config.highpass_freq is not None:
                effects.append(HighpassFilter(cutoff_frequency_hz=config.highpass_freq))

            # Create pedalboard
            board = Pedalboard(effects)  # type: ignore[arg-type]

            # Apply pedalboard effects
            if effects:
                audio = board(audio, sample_rate)

            # Load and apply NAM model
            nam_model, model_sample_rate = load_nam_model(config.nam_model_path)

            # Resample for NAM if needed
            if sample_rate != model_sample_rate:
                num_samples = int(len(audio) * model_sample_rate / sample_rate)
                audio = signal.resample(audio, num_samples)
                sample_rate = model_sample_rate

            # Apply NAM model
            audio = self._apply_nam_model(nam_model, audio)

            # Apply IR if configured
            if config.ir_path is not None:
                ir_convolution = load_ir(config.ir_path)
                audio = ir_convolution(audio, sample_rate)

            # Normalize loudness
            meter = pyln.Meter(sample_rate)
            current_lufs = meter.integrated_loudness(audio)
            audio = pyln.normalize.loudness(audio, current_lufs, config.target_lufs)

            # Write output file
            sf.write(output_path, audio, sample_rate)

            # Calculate output metrics
            duration = float(len(audio)) / sample_rate
            peak = np.max(np.abs(audio))
            peak_dbfs = 20 * np.log10(peak) if peak > 0 else -np.inf

            processing_time = time.time() - start_time

            return AudioResult.create(
                output_path=output_path,
                duration_seconds=duration,
                sample_rate=sample_rate,
                peak_dbfs=float(peak_dbfs),
                lufs_integrated=config.target_lufs,
                processing_time_seconds=processing_time,
            )

        except Exception as e:
            raise ProcessingError(f"Failed to process DI track: {e}") from e

    def _apply_nam_model(
        self,
        model: torch.nn.Module,
        audio: np.ndarray,
    ) -> np.ndarray:
        """Apply NAM model to audio.

        Args:
            model: Loaded NAM PyTorch model
            audio: Input audio samples

        Returns:
            Processed audio samples

        Note:
            This is a simplified implementation that processes audio sample-by-sample.
            Real NAM models would use proper buffering and batch processing for efficiency.
        """
        # Convert audio to tensor (shape: [num_samples])
        audio_tensor = torch.from_numpy(audio).float()

        # Process sample-by-sample (simplified approach for testing)
        # Real NAM models would process in chunks for efficiency
        processed_samples = []

        with torch.no_grad():
            for sample in audio_tensor:
                # Reshape sample to (1, 1) for model input
                input_sample = sample.view(1, 1)
                output_sample = model(input_sample)
                processed_samples.append(output_sample.item())

        # Convert back to numpy array
        processed = np.array(processed_samples, dtype=np.float32)

        return processed
