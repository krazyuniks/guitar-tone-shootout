"""T3K-specific value objects.

These enums represent T3K-specific platform types and gear classifications.
They are NOT part of the core domain - they represent data as it exists
in the Tone3000 system before transformation to GTS format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class T3KPlatform(str, Enum):
    """Platform type in the T3K system.

    T3K uses these platforms to categorise their tones.
    These are mapped to core Platform enum during synchronisation.
    """

    NAM = "nam"
    AIDA_X = "aida-x"
    IR = "ir"
    AA_SNAPSHOT = "aa-snapshot"
    PROTEUS = "proteus"


class T3KGearKind(str, Enum):
    """Gear kind classification in the T3K system.

    T3K uses these types to categorise tones by gear type.
    These are mapped to core GearType during synchronisation.
    Values match the real T3K API responses.
    """

    AMP = "amp"
    PEDAL = "pedal"
    FULL_RIG = "full-rig"
    OUTBOARD = "outboard"
    IR = "ir"


class SyncMode(str, Enum):
    """Sync mode controlling how the batch processes tones."""

    CATCH_UP = "catch_up"
    BAU = "bau"


@dataclass(frozen=True, slots=True)
class TonePackageResult:
    """Result of processing a single tone in a sync batch."""

    tone_id: int
    models_staged: int = 0
    files_downloaded: int = 0
    api_calls: int = 0
    skipped: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SyncBatchResult:
    """Result of a complete sync batch run."""

    mode: SyncMode
    page: int
    tones_processed: int = 0
    tones_skipped: int = 0
    models_staged: int = 0
    files_downloaded: int = 0
    api_calls_made: int = 0
    api_calls_failed: int = 0
    hit_known_tone: bool = False
    reached_end: bool = False
    tone_results: list[TonePackageResult] = field(default_factory=list)
