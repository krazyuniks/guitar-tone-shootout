"""Tone 3000 API schemas for tones and models."""

from enum import Enum

from pydantic import BaseModel


class Gear(str, Enum):
    """Type of gear the tone represents."""

    AMP = "amp"
    FULL_RIG = "full-rig"
    PEDAL = "pedal"
    OUTBOARD = "outboard"
    IR = "ir"


class Platform(str, Enum):
    """Target platform for the model."""

    NAM = "nam"
    IR = "ir"
    AIDA_X = "aida-x"


class ModelSize(str, Enum):
    """NAM model size variants."""

    STANDARD = "standard"
    LITE = "lite"
    FEATHER = "feather"
    NANO = "nano"


class Tag(BaseModel):
    """Tag from Tone 3000."""

    id: int
    name: str


class Make(BaseModel):
    """Manufacturer/Make from Tone 3000."""

    id: int
    name: str


class Tone(BaseModel):
    """Tone from Tone 3000 API."""

    id: int
    title: str
    description: str | None = None
    gear: Gear
    platform: Platform
    tags: list[Tag] = []
    makes: list[Make] = []
    models_count: int = 0
    downloads_count: int = 0


class Model(BaseModel):
    """Downloadable model from Tone 3000."""

    id: int
    name: str
    size: ModelSize
    model_url: str  # Pre-signed download URL
    tone_id: int


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    data: list[Tone]
    total: int
    page: int
    per_page: int
    has_next: bool
