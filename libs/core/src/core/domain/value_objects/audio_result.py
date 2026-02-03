"""AudioResult value object for domain layer.

Result of audio processing operations.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AudioResult:
    """Value object representing the result of audio processing.

    This is an immutable value object containing metadata about
    processed audio output.

    Attributes:
        output_path: Path to the processed audio file
        duration_seconds: Duration of the audio in seconds
        sample_rate: Sample rate of the output audio in Hz
        peak_dbfs: Peak level in dB relative to full scale
        lufs_integrated: Integrated loudness in LUFS (EBU R128)
        processing_time_seconds: Time taken to process in seconds
        processed_at: Timestamp when processing completed
    """

    output_path: Path
    duration_seconds: float
    sample_rate: int
    peak_dbfs: float
    lufs_integrated: float
    processing_time_seconds: float
    processed_at: datetime

    @classmethod
    def create(
        cls,
        output_path: Path,
        duration_seconds: float,
        sample_rate: int,
        peak_dbfs: float,
        lufs_integrated: float,
        processing_time_seconds: float,
    ) -> "AudioResult":
        """Create an AudioResult with the current timestamp.

        Args:
            output_path: Path to the processed audio file
            duration_seconds: Duration of the audio in seconds
            sample_rate: Sample rate of the output audio in Hz
            peak_dbfs: Peak level in dB relative to full scale
            lufs_integrated: Integrated loudness in LUFS
            processing_time_seconds: Time taken to process in seconds

        Returns:
            A new AudioResult instance with processed_at set to now
        """
        return cls(
            output_path=output_path,
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            peak_dbfs=peak_dbfs,
            lufs_integrated=lufs_integrated,
            processing_time_seconds=processing_time_seconds,
            processed_at=datetime.now(UTC),
        )

    def is_clipping(self, threshold_dbfs: float = -0.1) -> bool:
        """Check if the audio is clipping based on peak level.

        Args:
            threshold_dbfs: Threshold in dBFS above which audio is considered
                clipping. Default is -0.1 dBFS.

        Returns:
            True if peak_dbfs is above the threshold, False otherwise
        """
        return self.peak_dbfs > threshold_dbfs
