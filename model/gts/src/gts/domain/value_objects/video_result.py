"""VideoResult value object for domain layer.

Result of video composition operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gts.domain.value_objects.chapter_marker import ChapterMarker

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoResult:
    """Value object representing the result of video composition.

    This is an immutable value object containing metadata about
    composed video output.

    Attributes:
        output_path: Path to the composed video file
        duration_seconds: Total duration of the video in seconds
        resolution: Video resolution as "widthxheight" (e.g., "1920x1080")
        codec: Video codec used (e.g., "h264", "vp9")
        frame_rate: Video frame rate in fps
        segment_count: Number of segments in the composition
        file_size_bytes: Size of the output file in bytes
        processing_time_seconds: Time taken to compose in seconds
        composed_at: Timestamp when composition completed
        chapters: List of chapter markers for video navigation
        youtube_description: Pre-formatted chapter text for YouTube description
    """

    output_path: Path
    duration_seconds: float
    resolution: str
    codec: str
    frame_rate: float
    segment_count: int
    file_size_bytes: int
    processing_time_seconds: float
    composed_at: datetime
    chapters: tuple[ChapterMarker, ...] | None = None
    youtube_description: str | None = None

    @classmethod
    def create(
        cls,
        output_path: Path,
        duration_seconds: float,
        resolution: str,
        codec: str,
        frame_rate: float,
        segment_count: int,
        file_size_bytes: int,
        processing_time_seconds: float,
        chapters: list[ChapterMarker] | None = None,
    ) -> VideoResult:
        """Create a VideoResult with the current timestamp.

        Args:
            output_path: Path to the composed video file
            duration_seconds: Total duration of the video in seconds
            resolution: Video resolution as "widthxheight"
            codec: Video codec used
            frame_rate: Video frame rate in fps
            segment_count: Number of segments in the composition
            file_size_bytes: Size of the output file in bytes
            processing_time_seconds: Time taken to compose in seconds
            chapters: Optional list of chapter markers

        Returns:
            A new VideoResult instance with composed_at set to now
        """
        youtube_desc = None
        chapters_tuple = None
        if chapters:
            chapters_tuple = tuple(chapters)
            youtube_desc = ChapterMarker.to_youtube_description(chapters)

        return cls(
            output_path=output_path,
            duration_seconds=duration_seconds,
            resolution=resolution,
            codec=codec,
            frame_rate=frame_rate,
            segment_count=segment_count,
            file_size_bytes=file_size_bytes,
            processing_time_seconds=processing_time_seconds,
            composed_at=datetime.now(UTC),
            chapters=chapters_tuple,
            youtube_description=youtube_desc,
        )

    @property
    def width(self) -> int:
        """Extract width from resolution string.

        Returns:
            Video width in pixels
        """
        return int(self.resolution.split("x")[0])

    @property
    def height(self) -> int:
        """Extract height from resolution string.

        Returns:
            Video height in pixels
        """
        return int(self.resolution.split("x")[1])

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio.

        Returns:
            Aspect ratio as width/height
        """
        return self.width / self.height

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes.

        Returns:
            File size in MB
        """
        return self.file_size_bytes / (1024 * 1024)
