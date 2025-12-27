"""Tests for segment timestamp tracking."""

from __future__ import annotations

import pytest

from guitar_tone_shootout.timestamps import (
    SegmentTimestamps,
    SegmentTimestampsSchema,
    SegmentTracker,
    compute_segment_timestamps,
)


class TestSegmentTimestamps:
    """Tests for SegmentTimestamps dataclass."""

    def test_from_samples_basic(self) -> None:
        """Test creating timestamps from sample positions."""
        ts = SegmentTimestamps.from_samples(
            position=0,
            start_sample=0,
            end_sample=48000,
            sample_rate=48000,
        )

        assert ts.position == 0
        assert ts.start_ms == 0
        assert ts.end_ms == 1000  # 48000 samples @ 48kHz = 1 second
        assert ts.duration_ms == 1000
        assert ts.source_start_sample == 0
        assert ts.source_end_sample == 48000
        assert ts.sample_rate == 48000

    def test_from_samples_with_offset(self) -> None:
        """Test creating timestamps with output offset."""
        ts = SegmentTimestamps.from_samples(
            position=1,
            start_sample=0,
            end_sample=48000,
            sample_rate=48000,
            output_offset_ms=3000,  # 3 second offset
        )

        assert ts.position == 1
        assert ts.start_ms == 3000
        assert ts.end_ms == 4000
        assert ts.duration_ms == 1000

    def test_from_samples_fractional_duration(self) -> None:
        """Test with fractional durations."""
        # 168480 samples @ 48kHz = 3.51 seconds = 3510 ms
        ts = SegmentTimestamps.from_samples(
            position=0,
            start_sample=0,
            end_sample=168480,
            sample_rate=48000,
        )

        assert ts.duration_ms == 3510
        assert ts.end_ms == 3510

    def test_from_duration_ms(self) -> None:
        """Test creating timestamps from duration in milliseconds."""
        ts = SegmentTimestamps.from_duration_ms(
            position=0,
            duration_ms=2500,
            sample_rate=48000,
        )

        assert ts.position == 0
        assert ts.start_ms == 0
        assert ts.end_ms == 2500
        assert ts.duration_ms == 2500
        assert ts.sample_rate == 48000
        # Duration in samples: 2500ms * 48 samples/ms = 120000
        assert ts.source_end_sample == 120000

    def test_from_duration_ms_with_offset(self) -> None:
        """Test duration-based creation with offset."""
        ts = SegmentTimestamps.from_duration_ms(
            position=2,
            duration_ms=1500,
            sample_rate=44100,
            output_offset_ms=5000,
        )

        assert ts.start_ms == 5000
        assert ts.end_ms == 6500
        assert ts.duration_ms == 1500

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        ts = SegmentTimestamps.from_samples(
            position=0,
            start_sample=0,
            end_sample=48000,
            sample_rate=48000,
        )

        data = ts.to_dict()

        assert data == {
            "position": 0,
            "start_ms": 0,
            "end_ms": 1000,
            "duration_ms": 1000,
            "source_start_sample": 0,
            "source_end_sample": 48000,
            "sample_rate": 48000,
        }


class TestSegmentTracker:
    """Tests for SegmentTracker class."""

    def test_empty_tracker(self) -> None:
        """Test empty tracker state."""
        tracker = SegmentTracker(sample_rate=48000)

        assert tracker.segment_count == 0
        assert tracker.total_duration_ms == 0
        assert tracker.segments == []

    def test_add_single_segment(self) -> None:
        """Test adding a single segment."""
        tracker = SegmentTracker(sample_rate=48000)

        ts = tracker.add_segment(duration_samples=48000)

        assert tracker.segment_count == 1
        assert tracker.total_duration_ms == 1000
        assert ts.position == 0
        assert ts.start_ms == 0
        assert ts.end_ms == 1000

    def test_add_multiple_segments(self) -> None:
        """Test adding multiple segments with cumulative offsets."""
        tracker = SegmentTracker(sample_rate=48000)

        ts1 = tracker.add_segment(duration_samples=48000)  # 1 second
        ts2 = tracker.add_segment(duration_samples=96000)  # 2 seconds
        ts3 = tracker.add_segment(duration_samples=24000)  # 0.5 seconds

        assert tracker.segment_count == 3
        assert tracker.total_duration_ms == 3500

        # First segment
        assert ts1.position == 0
        assert ts1.start_ms == 0
        assert ts1.end_ms == 1000

        # Second segment
        assert ts2.position == 1
        assert ts2.start_ms == 1000
        assert ts2.end_ms == 3000

        # Third segment
        assert ts3.position == 2
        assert ts3.start_ms == 3000
        assert ts3.end_ms == 3500

    def test_add_segment_duration_ms(self) -> None:
        """Test adding segment with millisecond duration."""
        tracker = SegmentTracker(sample_rate=48000)

        ts = tracker.add_segment(duration_ms=2500)

        assert ts.duration_ms == 2500
        assert ts.start_ms == 0
        assert ts.end_ms == 2500

    def test_add_segment_requires_duration(self) -> None:
        """Test that either duration_samples or duration_ms is required."""
        tracker = SegmentTracker(sample_rate=48000)

        with pytest.raises(ValueError, match="duration"):
            tracker.add_segment()

    def test_get_segment_valid(self) -> None:
        """Test getting segment by position."""
        tracker = SegmentTracker(sample_rate=48000)
        tracker.add_segment(duration_ms=1000)
        tracker.add_segment(duration_ms=2000)

        seg = tracker.get_segment(1)

        assert seg is not None
        assert seg.position == 1
        assert seg.duration_ms == 2000

    def test_get_segment_invalid(self) -> None:
        """Test getting invalid segment position."""
        tracker = SegmentTracker(sample_rate=48000)
        tracker.add_segment(duration_ms=1000)

        assert tracker.get_segment(5) is None
        assert tracker.get_segment(-1) is None

    def test_to_list(self) -> None:
        """Test converting all segments to list."""
        tracker = SegmentTracker(sample_rate=48000)
        tracker.add_segment(duration_ms=1000)
        tracker.add_segment(duration_ms=2000)

        result = tracker.to_list()

        assert len(result) == 2
        assert result[0]["position"] == 0
        assert result[0]["duration_ms"] == 1000
        assert result[1]["position"] == 1
        assert result[1]["duration_ms"] == 2000


class TestSegmentTimestampsSchema:
    """Tests for Pydantic schema."""

    def test_from_dataclass(self) -> None:
        """Test creating schema from dataclass."""
        ts = SegmentTimestamps.from_samples(
            position=0,
            start_sample=0,
            end_sample=48000,
            sample_rate=48000,
        )

        schema = SegmentTimestampsSchema.from_dataclass(ts)

        assert schema.position == 0
        assert schema.start_ms == 0
        assert schema.end_ms == 1000
        assert schema.duration_ms == 1000
        assert schema.sample_rate == 48000

    def test_schema_json_serialization(self) -> None:
        """Test JSON serialization of schema."""
        schema = SegmentTimestampsSchema(
            position=0,
            start_ms=0,
            end_ms=1000,
            duration_ms=1000,
            source_start_sample=0,
            source_end_sample=48000,
            sample_rate=48000,
        )

        json_str = schema.model_dump_json()

        assert "position" in json_str
        assert "start_ms" in json_str
        assert "sample_rate" in json_str

    def test_schema_validation(self) -> None:
        """Test schema validation constraints."""
        # Valid schema
        schema = SegmentTimestampsSchema(
            position=0,
            start_ms=0,
            end_ms=1000,
            duration_ms=1000,
            source_start_sample=0,
            source_end_sample=48000,
            sample_rate=48000,
        )
        assert schema is not None

        # Invalid: negative position
        with pytest.raises(ValueError):
            SegmentTimestampsSchema(
                position=-1,
                start_ms=0,
                end_ms=1000,
                duration_ms=1000,
                source_start_sample=0,
                source_end_sample=48000,
                sample_rate=48000,
            )

        # Invalid: zero sample rate
        with pytest.raises(ValueError):
            SegmentTimestampsSchema(
                position=0,
                start_ms=0,
                end_ms=1000,
                duration_ms=1000,
                source_start_sample=0,
                source_end_sample=48000,
                sample_rate=0,
            )


class TestComputeSegmentTimestamps:
    """Tests for compute_segment_timestamps utility."""

    def test_empty_list(self) -> None:
        """Test with empty duration list."""
        result = compute_segment_timestamps([])
        assert result == []

    def test_single_duration(self) -> None:
        """Test with single duration."""
        result = compute_segment_timestamps([3000], sample_rate=48000)

        assert len(result) == 1
        assert result[0].duration_ms == 3000
        assert result[0].start_ms == 0
        assert result[0].end_ms == 3000

    def test_multiple_durations(self) -> None:
        """Test with multiple durations."""
        result = compute_segment_timestamps(
            [1000, 2000, 1500],
            sample_rate=44100,
        )

        assert len(result) == 3

        assert result[0].start_ms == 0
        assert result[0].end_ms == 1000

        assert result[1].start_ms == 1000
        assert result[1].end_ms == 3000

        assert result[2].start_ms == 3000
        assert result[2].end_ms == 4500

    def test_sample_rate_propagated(self) -> None:
        """Test that sample rate is propagated to all segments."""
        result = compute_segment_timestamps(
            [1000, 2000],
            sample_rate=96000,
        )

        assert all(ts.sample_rate == 96000 for ts in result)
