"""WaveformData value object for domain layer.

Represents waveform visualization data for audio files.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WaveformData:
    """Value object representing waveform visualization data.

    This is an immutable value object containing downsampled waveform
    data suitable for UI visualization.

    Attributes:
        peaks: Tuple of peak values (normalized to -1.0 to 1.0)
        sample_rate: Original sample rate of the audio
        duration_seconds: Duration of the audio in seconds
        samples_per_peak: Number of original samples per peak value
    """

    peaks: tuple[float, ...]
    sample_rate: int
    duration_seconds: float
    samples_per_peak: int

    @property
    def peak_count(self) -> int:
        """Return the number of peak values."""
        return len(self.peaks)

    @property
    def max_peak(self) -> float:
        """Return the maximum peak value."""
        if not self.peaks:
            return 0.0
        return max(abs(p) for p in self.peaks)

    @property
    def is_clipping(self) -> bool:
        """Check if any peaks indicate clipping (>= 1.0)."""
        return self.max_peak >= 1.0

    def normalized(self) -> "WaveformData":
        """Return a copy with peaks normalized to max 1.0.

        Returns:
            A new WaveformData with normalized peaks
        """
        max_val = self.max_peak
        if max_val == 0:
            return self

        normalized_peaks = tuple(p / max_val for p in self.peaks)
        return WaveformData(
            peaks=normalized_peaks,
            sample_rate=self.sample_rate,
            duration_seconds=self.duration_seconds,
            samples_per_peak=self.samples_per_peak,
        )

    def to_list(self) -> list[float]:
        """Convert peaks to a list for JSON serialization."""
        return list(self.peaks)

    @classmethod
    def from_list(
        cls,
        peaks: list[float],
        sample_rate: int,
        duration_seconds: float,
        samples_per_peak: int,
    ) -> "WaveformData":
        """Create from a list of peaks.

        Args:
            peaks: List of peak values
            sample_rate: Original sample rate
            duration_seconds: Audio duration
            samples_per_peak: Samples per peak

        Returns:
            A new WaveformData instance
        """
        return cls(
            peaks=tuple(peaks),
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            samples_per_peak=samples_per_peak,
        )
