"""Shootout metadata capture for 100% reproducibility.

This module provides data structures and utilities for capturing all
processing information needed to reproduce a shootout exactly, including:

- Software versions (pedalboard, NAM, FFmpeg, pipeline, Python)
- Audio settings (sample rate, bit depth, channels)
- Normalization settings (target levels, method)
- File hashes (DI track, NAM models, IRs)

Example:
    >>> from guitar_tone_shootout.metadata import (
    ...     ProcessingMetadata, collect_processing_versions
    ... )
    >>> versions = collect_processing_versions()
    >>> print(f"Pipeline: {versions.pipeline}")
    >>> print(f"Python: {versions.python}")
"""

from __future__ import annotations

import hashlib
import logging
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Version Information
# =============================================================================


@dataclass
class ProcessingVersions:
    """Software versions used during processing.

    Attributes:
        pedalboard: Pedalboard library version (audio effects)
        nam_vst: NAM VST/JUCE version (Neural Amp Modeler)
        ffmpeg: FFmpeg version (audio/video encoding)
        pipeline: Guitar Tone Shootout pipeline version
        python: Python interpreter version
    """

    pedalboard: str
    nam_vst: str
    ffmpeg: str
    pipeline: str
    python: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pedalboard": self.pedalboard,
            "nam_vst": self.nam_vst,
            "ffmpeg": self.ffmpeg,
            "pipeline": self.pipeline,
            "python": self.python,
        }


def get_pedalboard_version() -> str:
    """Get installed pedalboard version."""
    try:
        import pedalboard

        return getattr(pedalboard, "__version__", "unknown")
    except ImportError:
        return "not installed"


def get_nam_version() -> str:
    """Get NAM VST/library version.

    NAM doesn't have a Python package version, so we check for
    the neural-amp-modeler or nam packages.
    """
    try:
        import nam

        return getattr(nam, "__version__", "unknown")
    except ImportError:
        pass

    try:
        import neural_amp_modeler

        return getattr(neural_amp_modeler, "__version__", "unknown")
    except ImportError:
        pass

    return "unknown"


def get_ffmpeg_version() -> str:
    """Get FFmpeg version from command line."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Parse first line: "ffmpeg version 6.1.1 Copyright ..."
        first_line = result.stdout.split("\n")[0]
        parts = first_line.split()
        if len(parts) >= 3 and parts[0] == "ffmpeg":
            return parts[2]
        return "unknown"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return "not installed"


def get_pipeline_version() -> str:
    """Get Guitar Tone Shootout pipeline version."""
    try:
        from guitar_tone_shootout import __version__

        return __version__
    except ImportError:
        return "unknown"


def get_python_version() -> str:
    """Get Python interpreter version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def collect_processing_versions() -> ProcessingVersions:
    """Collect all processing software versions.

    Returns:
        ProcessingVersions with all version information
    """
    return ProcessingVersions(
        pedalboard=get_pedalboard_version(),
        nam_vst=get_nam_version(),
        ffmpeg=get_ffmpeg_version(),
        pipeline=get_pipeline_version(),
        python=get_python_version(),
    )


# =============================================================================
# Audio Settings
# =============================================================================


@dataclass
class AudioSettings:
    """Audio processing settings for reproducibility.

    Attributes:
        sample_rate: Sample rate in Hz (e.g., 48000)
        bit_depth: Bit depth (e.g., 32 for float32)
        channels: Number of audio channels (1=mono, 2=stereo)
        format: Audio format (e.g., "float32", "int16")
    """

    sample_rate: int
    bit_depth: int
    channels: int
    format: str = "float32"

    def to_dict(self) -> dict[str, int | str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sample_rate": self.sample_rate,
            "bit_depth": self.bit_depth,
            "channels": self.channels,
            "format": self.format,
        }


# =============================================================================
# Normalization Settings
# =============================================================================


@dataclass
class NormalizationSettings:
    """Audio normalization settings for reproducibility.

    Attributes:
        input_target_rms_db: Input normalization target RMS in dB
        output_target_rms_db: Output normalization target RMS in dB
        method: Normalization method ("rms", "lufs", "peak", "none")
        headroom_db: Headroom for peak limiting in dB
    """

    input_target_rms_db: float = -18.0
    output_target_rms_db: float = -14.0
    method: str = "rms"
    headroom_db: float = -1.0

    def to_dict(self) -> dict[str, float | str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_target_rms_db": self.input_target_rms_db,
            "output_target_rms_db": self.output_target_rms_db,
            "method": self.method,
            "headroom_db": self.headroom_db,
        }


# =============================================================================
# File Hashes
# =============================================================================


@dataclass
class FileHashes:
    """SHA-256 hashes of input files for reproducibility verification.

    Attributes:
        di_track_sha256: Hash of the DI track audio file
        nam_model_sha256: Hash of the NAM model file (or None if not used)
        ir_sha256: Hash of the IR file (or None if not used)
    """

    di_track_sha256: str
    nam_model_sha256: str | None = None
    ir_sha256: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary for JSON serialization."""
        return {
            "di_track_sha256": self.di_track_sha256,
            "nam_model_sha256": self.nam_model_sha256,
            "ir_sha256": self.ir_sha256,
        }


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA-256 hash string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    import pathlib

    sha256 = hashlib.sha256()
    with pathlib.Path(file_path).open("rb") as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_file_hashes(
    di_track: Path,
    nam_model: Path | None = None,
    ir_file: Path | None = None,
) -> FileHashes:
    """Compute hashes for all input files.

    Args:
        di_track: Path to DI track audio file
        nam_model: Optional path to NAM model file
        ir_file: Optional path to IR file

    Returns:
        FileHashes with computed SHA-256 hashes
    """
    di_hash = compute_file_hash(di_track)
    nam_hash = compute_file_hash(nam_model) if nam_model else None
    ir_hash = compute_file_hash(ir_file) if ir_file else None

    return FileHashes(
        di_track_sha256=di_hash,
        nam_model_sha256=nam_hash,
        ir_sha256=ir_hash,
    )


# =============================================================================
# Complete Processing Metadata
# =============================================================================


@dataclass
class ProcessingMetadata:
    """Complete processing metadata for 100% reproducibility.

    Combines all metadata categories into a single structure that can
    be stored in the database and used to verify or reproduce processing.

    Attributes:
        versions: Software versions used
        audio_settings: Audio processing settings
        normalization: Normalization settings
        file_hashes: Input file hashes
        processed_at: ISO timestamp of processing
        processing_duration_seconds: Time taken to process
        total_duration_ms: Total output audio duration
        segment_count: Number of segments processed
        platform_info: Platform/OS information
    """

    versions: ProcessingVersions
    audio_settings: AudioSettings
    normalization: NormalizationSettings
    file_hashes: FileHashes
    processed_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    processing_duration_seconds: float | None = None
    total_duration_ms: int = 0
    segment_count: int = 0
    platform_info: str = field(default_factory=lambda: f"{platform.system()} {platform.release()}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization/database storage."""
        return {
            "versions": self.versions.to_dict(),
            "audio_settings": self.audio_settings.to_dict(),
            "normalization": self.normalization.to_dict(),
            "file_hashes": self.file_hashes.to_dict(),
            "processed_at": self.processed_at,
            "processing_duration_seconds": self.processing_duration_seconds,
            "total_duration_ms": self.total_duration_ms,
            "segment_count": self.segment_count,
            "platform_info": self.platform_info,
        }


# =============================================================================
# Pydantic Schemas for API Integration
# =============================================================================


class ProcessingVersionsSchema(BaseModel):
    """Pydantic schema for processing versions."""

    pedalboard: str = Field(..., description="Pedalboard library version")
    nam_vst: str = Field(..., description="NAM VST/library version")
    ffmpeg: str = Field(..., description="FFmpeg version")
    pipeline: str = Field(..., description="Pipeline version")
    python: str = Field(..., description="Python version")


class AudioSettingsSchema(BaseModel):
    """Pydantic schema for audio settings."""

    sample_rate: int = Field(..., gt=0, description="Sample rate in Hz")
    bit_depth: int = Field(..., gt=0, description="Bit depth")
    channels: int = Field(..., ge=1, le=2, description="Number of channels")
    format: str = Field(default="float32", description="Audio format")


class NormalizationSettingsSchema(BaseModel):
    """Pydantic schema for normalization settings."""

    input_target_rms_db: float = Field(
        default=-18.0, description="Input normalization target RMS in dB"
    )
    output_target_rms_db: float = Field(
        default=-14.0, description="Output normalization target RMS in dB"
    )
    method: str = Field(default="rms", description="Normalization method")
    headroom_db: float = Field(default=-1.0, description="Peak headroom in dB")


class FileHashesSchema(BaseModel):
    """Pydantic schema for file hashes."""

    di_track_sha256: str = Field(..., description="SHA-256 hash of DI track")
    nam_model_sha256: str | None = Field(
        default=None, description="SHA-256 hash of NAM model"
    )
    ir_sha256: str | None = Field(default=None, description="SHA-256 hash of IR file")


class ProcessingMetadataFullSchema(BaseModel):
    """Complete processing metadata schema for API responses.

    This is a more detailed schema than ProcessingMetadataSchema in shootout.py,
    used specifically for the /metadata endpoint.
    """

    versions: ProcessingVersionsSchema = Field(
        ..., description="Software versions used"
    )
    audio_settings: AudioSettingsSchema = Field(
        ..., description="Audio processing settings"
    )
    normalization: NormalizationSettingsSchema = Field(
        ..., description="Normalization settings"
    )
    file_hashes: FileHashesSchema = Field(..., description="Input file hashes")
    processed_at: str = Field(..., description="ISO timestamp of processing")
    processing_duration_seconds: float | None = Field(
        default=None, description="Processing time in seconds"
    )
    total_duration_ms: int = Field(default=0, ge=0, description="Total output duration")
    segment_count: int = Field(default=0, ge=0, description="Number of segments")
    platform_info: str = Field(default="", description="Platform/OS information")

    @classmethod
    def from_dataclass(cls, metadata: ProcessingMetadata) -> ProcessingMetadataFullSchema:
        """Create schema from dataclass instance."""
        return cls(
            versions=ProcessingVersionsSchema(
                pedalboard=metadata.versions.pedalboard,
                nam_vst=metadata.versions.nam_vst,
                ffmpeg=metadata.versions.ffmpeg,
                pipeline=metadata.versions.pipeline,
                python=metadata.versions.python,
            ),
            audio_settings=AudioSettingsSchema(
                sample_rate=metadata.audio_settings.sample_rate,
                bit_depth=metadata.audio_settings.bit_depth,
                channels=metadata.audio_settings.channels,
                format=metadata.audio_settings.format,
            ),
            normalization=NormalizationSettingsSchema(
                input_target_rms_db=metadata.normalization.input_target_rms_db,
                output_target_rms_db=metadata.normalization.output_target_rms_db,
                method=metadata.normalization.method,
                headroom_db=metadata.normalization.headroom_db,
            ),
            file_hashes=FileHashesSchema(
                di_track_sha256=metadata.file_hashes.di_track_sha256,
                nam_model_sha256=metadata.file_hashes.nam_model_sha256,
                ir_sha256=metadata.file_hashes.ir_sha256,
            ),
            processed_at=metadata.processed_at,
            processing_duration_seconds=metadata.processing_duration_seconds,
            total_duration_ms=metadata.total_duration_ms,
            segment_count=metadata.segment_count,
            platform_info=metadata.platform_info,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def create_processing_metadata(
    di_track: Path,
    sample_rate: int = 48000,
    bit_depth: int = 32,
    channels: int = 2,
    nam_model: Path | None = None,
    ir_file: Path | None = None,
    normalization: NormalizationSettings | None = None,
) -> ProcessingMetadata:
    """Create processing metadata by collecting all information.

    Convenience function that gathers all metadata in one call.

    Args:
        di_track: Path to DI track audio file
        sample_rate: Audio sample rate
        bit_depth: Audio bit depth
        channels: Number of channels
        nam_model: Optional NAM model path
        ir_file: Optional IR file path
        normalization: Optional normalization settings

    Returns:
        Complete ProcessingMetadata instance
    """
    versions = collect_processing_versions()

    audio_settings = AudioSettings(
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
    )

    if normalization is None:
        normalization = NormalizationSettings()

    file_hashes = compute_file_hashes(di_track, nam_model, ir_file)

    return ProcessingMetadata(
        versions=versions,
        audio_settings=audio_settings,
        normalization=normalization,
        file_hashes=file_hashes,
    )
