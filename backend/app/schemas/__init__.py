"""Pydantic schemas."""

from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobProgressUpdate,
    JobResponse,
)
from app.schemas.shootout import (
    EffectSchema,
    ShootoutConfigSchema,
    ShootoutCreate,
    ShootoutListResponse,
    ShootoutResponse,
    ShootoutSubmitRequest,
    ShootoutSubmitResponse,
    ShootoutUpdate,
    ToneSchema,
    ToneSelectionCreate,
    ToneSelectionResponse,
)

__all__ = [
    # Job schemas
    "JobCreate",
    "JobListResponse",
    "JobProgressUpdate",
    "JobResponse",
    # Shootout config schemas (for job submission)
    "EffectSchema",
    "ShootoutConfigSchema",
    "ShootoutSubmitRequest",
    "ShootoutSubmitResponse",
    "ToneSchema",
    # Shootout model schemas (for CRUD)
    "ShootoutCreate",
    "ShootoutListResponse",
    "ShootoutResponse",
    "ShootoutUpdate",
    "ToneSelectionCreate",
    "ToneSelectionResponse",
]
