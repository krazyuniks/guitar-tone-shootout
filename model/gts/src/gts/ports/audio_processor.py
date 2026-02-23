"""Audio processor port definition for domain layer.

Defines the interface for audio processing operations.
"""

from pathlib import Path
from typing import Protocol

from gts.domain.value_objects.audio_result import AudioResult
from gts.domain.value_objects.tone_config import ToneConfig
from gts.domain.value_objects.waveform_data import WaveformData


class AudioProcessor(Protocol):
    """Protocol for audio processing operations.

    This port defines the interface that the domain layer expects
    from audio processing implementations. The actual implementation
    lives in libs/audio.
    """

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
        ...

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
        ...

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
        ...

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
        ...

    def get_supported_formats(self) -> list[str]:
        """Get list of supported audio formats.

        Returns:
            List of format extensions (e.g., ['wav', 'flac', 'mp3'])
        """
        ...

    def is_format_supported(self, format_ext: str) -> bool:
        """Check if a format is supported.

        Args:
            format_ext: Format extension (without dot)

        Returns:
            True if supported, False otherwise
        """
        ...
