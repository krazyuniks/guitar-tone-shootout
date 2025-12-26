"""Domain models for audio processing resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003 - used in type hints at runtime
from enum import Enum
from pathlib import Path


class NAMModelSize(Enum):
    """NAM model size/architecture."""

    STANDARD = "standard"
    LITE = "lite"
    FEATHER = "feather"
    NANO = "nano"


class NAMModelType(Enum):
    """Type of NAM capture."""

    AMP_HEAD = "amp_head"
    AMP_COMBO = "amp_combo"
    PEDAL = "pedal"
    FULL_RIG = "full_rig"  # Amp + cab combined
    UNKNOWN = "unknown"


@dataclass
class NAMCapture:
    """
    Individual NAM model capture.

    Represents a single .nam file from a source like Tone3000.
    """

    name: str
    download_url: str
    esr: float  # Error-to-Signal Ratio (lower is better)
    epochs: int  # Training epochs
    size: NAMModelSize = NAMModelSize.STANDARD

    # Local storage
    local_path: Path | None = None

    # Optional metadata
    description: str = ""
    sweep_signal: str = "standard"
    training_status: str = "finished"

    @property
    def filename(self) -> str:
        """Generate safe filename from model name."""
        # Replace problematic chars, keep extension
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in self.name)
        if not safe.endswith(".nam"):
            safe += ".nam"
        return safe

    @property
    def is_downloaded(self) -> bool:
        """Check if model file exists locally."""
        return self.local_path is not None and self.local_path.exists()


@dataclass
class NAMTonePack:
    """
    Collection of NAM captures from a single source page.

    Represents a Tone3000 tone pack or similar collection.
    """

    # Source identification
    source: str  # e.g., "tone3000"
    page_url: str  # e.g., "https://www.tone3000.com/tones/mesa-dualrect--40093"
    slug: str  # e.g., "mesa-dualrect--40093"

    # Pack metadata
    title: str
    author: str
    model_type: NAMModelType = NAMModelType.UNKNOWN

    # Content
    captures: list[NAMCapture] = field(default_factory=list)

    # Optional metadata
    description: str = ""
    makes: list[str] = field(default_factory=list)  # e.g., ["Mesa Boogie"]
    models: list[str] = field(default_factory=list)  # e.g., ["Dual Rectifier"]
    tags: list[str] = field(default_factory=list)
    license: str = ""
    downloads: int = 0
    favorites: int = 0
    published_date: datetime | None = None

    def get_capture(self, name: str) -> NAMCapture | None:
        """Find a capture by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for capture in self.captures:
            if name_lower in capture.name.lower():
                return capture
        return None

    @property
    def local_dir(self) -> Path:
        """Local directory path for this tone pack."""
        return Path("inputs/nam_models") / self.source / self.slug


@dataclass
class ImpulseResponse:
    """
    Impulse Response (IR) for cabinet simulation.

    Flexible metadata to support various sources (Tone3000, commercial, forums).
    """

    name: str
    local_path: Path

    # Source info (optional - may be local/commercial)
    source: str = ""  # e.g., "tone3000", "ownhammer", "local"
    source_url: str = ""
    slug: str = ""

    # Cabinet metadata
    cabinet: str = ""  # e.g., "Mesa 4x12"
    speaker: str = ""  # e.g., "Celestion V30"
    microphone: str = ""  # e.g., "SM57"
    mic_position: str = ""  # e.g., "cap edge"

    # Creator info
    author: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        if self.cabinet and self.microphone:
            return f"{self.cabinet} ({self.microphone})"
        return self.name

    @property
    def is_available(self) -> bool:
        """Check if IR file exists locally."""
        return self.local_path.exists()


@dataclass
class DITrackInfo:
    """
    DI (Direct Input) track metadata.

    Enhanced metadata for source tracking and display.
    """

    name: str
    local_path: Path

    # Guitar info
    guitar: str = ""  # e.g., "Fender Stratocaster"
    pickup: str = ""  # e.g., "bridge single coil"
    strings: str = ""  # e.g., "Ernie Ball 10-46"
    tuning: str = ""  # e.g., "E Standard", "Drop D"

    # Recording info
    interface: str = ""  # e.g., "Focusrite Scarlett 2i2"
    sample_rate: int = 44100
    bit_depth: int = 24

    # Source/attribution
    source: str = ""  # e.g., "original", "splice", "user_submission"
    source_url: str = ""
    author: str = ""
    description: str = ""
    notes: str = ""

    # Content info
    genre: str = ""
    style: str = ""  # e.g., "rhythm", "lead", "clean arpeggios"
    bpm: int | None = None
    key: str = ""  # e.g., "E minor"

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        parts = [self.name]
        if self.guitar:
            parts.append(f"({self.guitar})")
        return " ".join(parts)

    @property
    def is_available(self) -> bool:
        """Check if DI track file exists locally."""
        return self.local_path.exists()
