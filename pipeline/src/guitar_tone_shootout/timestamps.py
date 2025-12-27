"""Segment timestamp tracking for audio processing.

This module provides data structures and utilities for tracking precise
start/end timestamps for each segment during pipeline processing, enabling:

- Accurate video chapter markers
- Segment-level audio analysis
- Reproducible segment extraction
- Timeline synchronization

Example:
    >>> from guitar_tone_shootout.timestamps import SegmentTimestamps, SegmentTracker
    >>> tracker = SegmentTracker(sample_rate=48000)
    >>> ts = tracker.add_segment(duration_samples=168480)  # 3.51 seconds
    >>> print(f"Segment {ts.position}: {ts.start_ms}ms - {ts.end_ms}ms")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class SegmentTimestamps:
    """Precise timing information for a processed audio segment.

    Tracks both the position in the final output (milliseconds) and the
    source sample positions for exact reproducibility.

    Attributes:
        position: Segment index (0-based) in the shootout
        start_ms: Start position in final output (milliseconds)
        end_ms: End position in final output (milliseconds)
        duration_ms: Segment duration (milliseconds)
        source_start_sample: Start sample index in source audio
        source_end_sample: End sample index in source audio
        sample_rate: Sample rate used for processing
    """

    position: int
    start_ms: int
    end_ms: int
    duration_ms: int
    source_start_sample: int
    source_end_sample: int
    sample_rate: int

    @classmethod
    def from_samples(
        cls,
        position: int,
        start_sample: int,
        end_sample: int,
        sample_rate: int,
        output_offset_ms: int = 0,
    ) -> SegmentTimestamps:
        """Create timestamps from sample positions.

        Args:
            position: Segment index in the shootout
            start_sample: Source start sample index
            end_sample: Source end sample index
            sample_rate: Sample rate in Hz
            output_offset_ms: Offset in output timeline (for concatenation)

        Returns:
            SegmentTimestamps with computed millisecond values
        """
        duration_samples = end_sample - start_sample
        duration_ms = int((duration_samples / sample_rate) * 1000)
        start_ms = output_offset_ms
        end_ms = output_offset_ms + duration_ms

        return cls(
            position=position,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
            source_start_sample=start_sample,
            source_end_sample=end_sample,
            sample_rate=sample_rate,
        )

    @classmethod
    def from_duration_ms(
        cls,
        position: int,
        duration_ms: int,
        sample_rate: int,
        output_offset_ms: int = 0,
    ) -> SegmentTimestamps:
        """Create timestamps from duration in milliseconds.

        Useful when source sample positions are not tracked.

        Args:
            position: Segment index in the shootout
            duration_ms: Duration in milliseconds
            sample_rate: Sample rate in Hz
            output_offset_ms: Offset in output timeline (for concatenation)

        Returns:
            SegmentTimestamps with computed values
        """
        start_ms = output_offset_ms
        end_ms = output_offset_ms + duration_ms
        duration_samples = int((duration_ms / 1000) * sample_rate)

        return cls(
            position=position,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
            source_start_sample=0,
            source_end_sample=duration_samples,
            sample_rate=sample_rate,
        )

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for JSON serialization."""
        return {
            "position": self.position,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "source_start_sample": self.source_start_sample,
            "source_end_sample": self.source_end_sample,
            "sample_rate": self.sample_rate,
        }


@dataclass
class SegmentTracker:
    """Tracks timestamps for multiple segments in a shootout.

    Manages the sequential addition of segments and computes
    cumulative offsets for the final concatenated output.

    Attributes:
        sample_rate: Sample rate for all segments
        segments: List of tracked segment timestamps
        total_duration_ms: Total duration of all segments
    """

    sample_rate: int
    segments: list[SegmentTimestamps] = field(default_factory=list)
    _current_offset_ms: int = field(default=0, repr=False)

    @property
    def total_duration_ms(self) -> int:
        """Total duration of all tracked segments in milliseconds."""
        if not self.segments:
            return 0
        return self.segments[-1].end_ms

    @property
    def segment_count(self) -> int:
        """Number of tracked segments."""
        return len(self.segments)

    def add_segment(
        self,
        duration_samples: int | None = None,
        duration_ms: int | None = None,
        start_sample: int = 0,
    ) -> SegmentTimestamps:
        """Add a new segment and return its timestamps.

        Provide either duration_samples or duration_ms.

        Args:
            duration_samples: Duration in samples
            duration_ms: Duration in milliseconds
            start_sample: Start sample in source audio

        Returns:
            SegmentTimestamps for the added segment

        Raises:
            ValueError: If neither duration_samples nor duration_ms provided
        """
        if duration_samples is None and duration_ms is None:
            msg = "Either duration_samples or duration_ms must be provided"
            raise ValueError(msg)

        position = len(self.segments)

        if duration_samples is not None:
            end_sample = start_sample + duration_samples
            timestamps = SegmentTimestamps.from_samples(
                position=position,
                start_sample=start_sample,
                end_sample=end_sample,
                sample_rate=self.sample_rate,
                output_offset_ms=self._current_offset_ms,
            )
        else:
            # duration_ms is not None due to check above
            timestamps = SegmentTimestamps.from_duration_ms(
                position=position,
                duration_ms=duration_ms,  # type: ignore[arg-type]
                sample_rate=self.sample_rate,
                output_offset_ms=self._current_offset_ms,
            )

        self.segments.append(timestamps)
        self._current_offset_ms = timestamps.end_ms

        return timestamps

    def get_segment(self, position: int) -> SegmentTimestamps | None:
        """Get timestamps for a specific segment by position."""
        if 0 <= position < len(self.segments):
            return self.segments[position]
        return None

    def to_list(self) -> list[dict[str, int]]:
        """Convert all segments to list of dictionaries."""
        return [seg.to_dict() for seg in self.segments]


# =============================================================================
# Pydantic Schemas for API Integration
# =============================================================================


class SegmentTimestampsSchema(BaseModel):
    """Pydantic schema for segment timestamps in API responses.

    Mirrors SegmentTimestamps dataclass for JSON serialization.
    """

    position: int = Field(
        ...,
        ge=0,
        description="Segment index (0-based) in the shootout",
    )
    start_ms: int = Field(
        ...,
        ge=0,
        description="Start position in final output (milliseconds)",
    )
    end_ms: int = Field(
        ...,
        ge=0,
        description="End position in final output (milliseconds)",
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Segment duration (milliseconds)",
    )
    source_start_sample: int = Field(
        ...,
        ge=0,
        description="Start sample index in source audio",
    )
    source_end_sample: int = Field(
        ...,
        ge=0,
        description="End sample index in source audio",
    )
    sample_rate: int = Field(
        ...,
        gt=0,
        description="Sample rate used for processing (Hz)",
    )

    @classmethod
    def from_dataclass(cls, ts: SegmentTimestamps) -> SegmentTimestampsSchema:
        """Create schema from dataclass instance."""
        return cls(
            position=ts.position,
            start_ms=ts.start_ms,
            end_ms=ts.end_ms,
            duration_ms=ts.duration_ms,
            source_start_sample=ts.source_start_sample,
            source_end_sample=ts.source_end_sample,
            sample_rate=ts.sample_rate,
        )


def compute_segment_timestamps(
    durations_ms: Sequence[int],
    sample_rate: int = 48000,
) -> list[SegmentTimestamps]:
    """Compute timestamps for a list of segment durations.

    Utility function for computing timestamps from a list of durations.

    Args:
        durations_ms: List of segment durations in milliseconds
        sample_rate: Sample rate for all segments

    Returns:
        List of SegmentTimestamps with cumulative offsets
    """
    tracker = SegmentTracker(sample_rate=sample_rate)

    for duration in durations_ms:
        tracker.add_segment(duration_ms=duration)

    return tracker.segments
