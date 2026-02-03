"""ChapterMarker value object for domain layer.

Represents YouTube-compatible chapter markers for shootout videos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class SegmentDuration(TypedDict):
    """Segment duration data for chapter calculation."""

    label: str
    duration_ms: int
    position: int


@dataclass(frozen=True, slots=True)
class ChapterMarker:
    """Value object representing a chapter marker for video.

    This is an immutable value object containing timing and label
    information for a chapter in a shootout video, compatible with
    YouTube's chapter format.

    Attributes:
        title: Display title for the chapter (e.g., tone name)
        start_ms: Start time in milliseconds from video start
        position: Order position in the video sequence (0-indexed)
    """

    title: str
    start_ms: int
    position: int

    @property
    def youtube_timestamp(self) -> str:
        """Format start time as YouTube-compatible timestamp.

        Returns:
            Timestamp in MM:SS format (or H:MM:SS if >= 1 hour)
        """
        total_seconds = self.start_ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def youtube_line(self) -> str:
        """Format as a single line for YouTube description.

        Returns:
            Line in format "MM:SS Title" for YouTube chapter
        """
        return f"{self.youtube_timestamp} {self.title}"

    @classmethod
    def from_segment_durations(
        cls, segments: list[SegmentDuration]
    ) -> list[ChapterMarker]:
        """Create chapter markers from segment duration data.

        Calculates cumulative start times based on segment durations,
        sorted by position.

        Args:
            segments: List of segment data with label, duration_ms, position

        Returns:
            List of ChapterMarker objects with calculated start times
        """
        # Sort by position
        sorted_segments = sorted(segments, key=lambda s: s["position"])

        markers: list[ChapterMarker] = []
        cumulative_ms = 0

        for segment in sorted_segments:
            markers.append(
                cls(
                    title=segment["label"],
                    start_ms=cumulative_ms,
                    position=segment["position"],
                )
            )
            cumulative_ms += segment["duration_ms"]

        return markers

    @staticmethod
    def to_youtube_description(markers: list[ChapterMarker]) -> str:
        """Format all markers as YouTube description chapter text.

        Args:
            markers: List of chapter markers

        Returns:
            Multi-line string suitable for YouTube video description
        """
        return "\n".join(marker.youtube_line for marker in markers)

    @staticmethod
    def to_ffmpeg_chapter_file(
        markers: list[ChapterMarker], total_duration_ms: int
    ) -> str:
        """Format markers as FFmpeg metadata chapter file content.

        Creates content for an FFmpeg chapter metadata file that can be
        used with -i metadata.txt to embed chapters in MP4.

        Args:
            markers: List of chapter markers
            total_duration_ms: Total video duration in milliseconds

        Returns:
            FFmpeg chapter metadata file content (FFMETADATA1 format)
        """
        lines = [";FFMETADATA1"]

        # Calculate end times for each chapter
        for i, marker in enumerate(markers):
            # End time is either the start of the next chapter or video end
            end_ms = markers[i + 1].start_ms if i + 1 < len(markers) else total_duration_ms

            lines.append("[CHAPTER]")
            lines.append("TIMEBASE=1/1000")
            lines.append(f"START={marker.start_ms}")
            lines.append(f"END={end_ms}")
            # Escape special characters in title for FFmpeg metadata
            escaped_title = (
                marker.title.replace("\\", "\\\\")
                .replace("=", "\\=")
                .replace(";", "\\;")
                .replace("#", "\\#")
                .replace("\n", "")
            )
            lines.append(f"title={escaped_title}")

        return "\n".join(lines)
