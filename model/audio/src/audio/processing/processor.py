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
from pedalboard import HighpassFilter, Pedalboard  # type: ignore[attr-defined]
from scipy import signal

from gts.domain.value_objects.audio_result import AudioResult
from gts.domain.value_objects.tone_config import ToneConfig
from gts.domain.value_objects.waveform_data import WaveformData

from ..analysis.waveform import extract_waveform as _extract_waveform
from .ir_loader import load_ir
from .loudness import measure_loudness as _measure_loudness
from .loudness import normalize_loudness as _normalize_loudness
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
        # Delegate to analysis module
        return _extract_waveform(audio_path, num_peaks=num_peaks)

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
        # Delegate to standalone loudness module
        return _measure_loudness(audio_path)

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

        # Delegate to standalone loudness module
        result_lufs, peak_dbfs = _normalize_loudness(input_path, output_path, target_lufs)

        # Load output file to get duration and sample rate
        audio, sample_rate = sf.read(output_path)
        duration = float(len(audio)) / sample_rate

        processing_time = time.time() - start_time

        return AudioResult.create(
            output_path=output_path,
            duration_seconds=duration,
            sample_rate=sample_rate,
            peak_dbfs=peak_dbfs,
            lufs_integrated=result_lufs,
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
            nam_model = load_nam_model(config.nam_model_path)

            # Resample for NAM if needed
            if nam_model.sample_rate and sample_rate != nam_model.sample_rate:
                num_samples = int(len(audio) * nam_model.sample_rate / sample_rate)
                audio = signal.resample(audio, num_samples)
                sample_rate = int(nam_model.sample_rate)

            # Apply NAM model (batch inference)
            audio = nam_model.process(audio.astype(np.float32))

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
