"""Video composer port definition for domain layer.

Defines the interface for video composition operations.
"""

from pathlib import Path
from typing import Protocol

from core.domain.value_objects.chapter_marker import ChapterMarker
from core.domain.value_objects.video_result import VideoResult


class VideoComposer(Protocol):
    """Protocol for video composition operations.

    This port defines the interface that the domain layer expects
    from video composition implementations. The actual implementation
    lives in libs/audio/video.
    """

    async def compose_shootout_video(
        self,
        audio_segments: list[tuple[Path, str]],
        output_path: Path,
        *,
        resolution: str = "1920x1080",
        codec: str = "h264",
        frame_rate: float = 30.0,
    ) -> VideoResult:
        """Compose a shootout comparison video.

        Creates a video with visual segments for each audio track,
        including chapter markers for navigation.

        Args:
            audio_segments: List of (audio_path, label) tuples
            output_path: Path for output video file
            resolution: Video resolution (widthxheight)
            codec: Video codec to use
            frame_rate: Video frame rate in fps

        Returns:
            VideoResult with composition metadata

        Raises:
            CompositionError: If composition fails
        """
        ...

    async def add_chapters_to_video(
        self,
        video_path: Path,
        output_path: Path,
        chapters: list[ChapterMarker],
    ) -> VideoResult:
        """Add chapter markers to an existing video.

        Args:
            video_path: Path to input video
            output_path: Path for output video
            chapters: List of chapter markers

        Returns:
            VideoResult with updated metadata
        """
        ...

    async def get_video_duration(self, video_path: Path) -> float:
        """Get the duration of a video in seconds.

        Args:
            video_path: Path to the video file

        Returns:
            Duration in seconds
        """
        ...

    async def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        *,
        format_ext: str = "wav",
    ) -> Path:
        """Extract audio track from video.

        Args:
            video_path: Path to input video
            output_path: Path for output audio
            format_ext: Output format extension

        Returns:
            Path to extracted audio file
        """
        ...

    def get_supported_codecs(self) -> list[str]:
        """Get list of supported video codecs.

        Returns:
            List of codec names (e.g., ['h264', 'h265', 'vp9'])
        """
        ...

    def get_supported_resolutions(self) -> list[str]:
        """Get list of recommended resolutions.

        Returns:
            List of resolution strings (e.g., ['1920x1080', '1280x720'])
        """
        ...
