"""ProcessingMetadata value object for domain layer.

This replaces the JSONB dict with a properly typed dataclass.
All 12 processing metadata fields are represented as flat fields for type safety.
"""

import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessingMetadata:
    """Value object representing processing metadata for reproducibility.

    This is an immutable value object containing all 12 processing metadata
    fields as properly typed fields (replacing the previous JSONB dict).

    Version info:
        pipeline_version: Version of the guitar-tone-shootout pipeline
        nam_version: Version of NAM (Neural Amp Modeler) used
        ffmpeg_version: Version of ffmpeg used for audio/video processing
        python_version: Python version used for processing

    Processing info:
        processed_at: Timestamp when processing completed
        processing_duration_seconds: Total processing time in seconds
        worker_id: Identifier of the worker that processed the job
        config_hash: Hash of the processing configuration for cache validation

    Audio/Video settings:
        audio_sample_rate: Sample rate in Hz
        audio_bit_depth: Bit depth of audio
        video_codec: Video codec used (e.g., 'h264', 'vp9')
        video_resolution: Video resolution (e.g., '1920x1080')
    """

    # Version info (pipeline_version is required, others optional)
    pipeline_version: str
    nam_version: str | None = None
    ffmpeg_version: str | None = None
    python_version: str | None = None

    # Processing info
    processed_at: datetime | None = None
    processing_duration_seconds: float | None = None
    worker_id: str | None = None
    config_hash: str | None = None

    # Audio/Video settings
    audio_sample_rate: int | None = None
    audio_bit_depth: int | None = None
    video_codec: str | None = None
    video_resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict format for API compatibility.

        Returns:
            A flat dict matching the legacy ProcessingMetadataSchema structure.
        """
        result: dict[str, Any] = {
            "pipeline_version": self.pipeline_version,
        }

        # Add optional version fields
        if self.nam_version is not None:
            result["nam_version"] = self.nam_version
        if self.ffmpeg_version is not None:
            result["ffmpeg_version"] = self.ffmpeg_version
        if self.python_version is not None:
            result["python_version"] = self.python_version

        # Add processing info
        if self.processed_at is not None:
            result["processed_at"] = self.processed_at.isoformat()
        if self.processing_duration_seconds is not None:
            result["processing_duration_seconds"] = self.processing_duration_seconds
        if self.worker_id is not None:
            result["worker_id"] = self.worker_id
        if self.config_hash is not None:
            result["config_hash"] = self.config_hash

        # Add audio/video settings as nested dicts for backward compatibility
        audio_settings: dict[str, Any] = {}
        if self.audio_sample_rate is not None:
            audio_settings["sample_rate"] = self.audio_sample_rate
        if self.audio_bit_depth is not None:
            audio_settings["bit_depth"] = self.audio_bit_depth
        if audio_settings:
            result["audio_settings"] = audio_settings

        video_settings: dict[str, Any] = {}
        if self.video_codec is not None:
            video_settings["codec"] = self.video_codec
        if self.video_resolution is not None:
            video_settings["resolution"] = self.video_resolution
        if video_settings:
            result["video_settings"] = video_settings

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessingMetadata":
        """Create from dict format (for parsing legacy JSONB or API input).

        Args:
            data: A dict matching the ProcessingMetadataSchema structure

        Returns:
            A ProcessingMetadata instance
        """
        # Extract audio_settings if present
        audio_settings = data.get("audio_settings", {})
        video_settings = data.get("video_settings", {})

        # Parse processed_at timestamp
        processed_at = None
        if data.get("processed_at"):
            processed_at_str = data["processed_at"]
            if isinstance(processed_at_str, str):
                # Try to parse ISO format timestamp
                with contextlib.suppress(ValueError):
                    processed_at = datetime.fromisoformat(
                        processed_at_str.replace("Z", "+00:00")
                    )
            elif isinstance(processed_at_str, datetime):
                processed_at = processed_at_str

        return cls(
            pipeline_version=data["pipeline_version"],
            nam_version=data.get("nam_version"),
            ffmpeg_version=data.get("ffmpeg_version"),
            python_version=data.get("python_version"),
            processed_at=processed_at,
            processing_duration_seconds=data.get("processing_duration_seconds"),
            worker_id=data.get("worker_id"),
            config_hash=data.get("config_hash"),
            audio_sample_rate=audio_settings.get("sample_rate"),
            audio_bit_depth=audio_settings.get("bit_depth"),
            video_codec=video_settings.get("codec"),
            video_resolution=video_settings.get("resolution"),
        )
