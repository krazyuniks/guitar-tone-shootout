"""Pydantic schemas."""

from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobProgressUpdate,
    JobResponse,
)
from app.schemas.shootout import (
    EffectSchema,
    MetricsAverages,
    SegmentComparisonItem,
    SegmentMetricsResponse,
    SegmentTimestampsSchema,
    ShootoutComparisonResponse,
    ShootoutConfigSchema,
    ShootoutCreate,
    ShootoutListItem,
    ShootoutListResponse,
    ShootoutMetadataResponse,
    ShootoutResponse,
    ShootoutSubmitRequest,
    ShootoutSubmitResponse,
    ShootoutUpdate,
    SignalChainSchema,
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
    "SegmentTimestampsSchema",
    "ShootoutCreate",
    "ShootoutListItem",
    "ShootoutListResponse",
    "ShootoutResponse",
    "ShootoutUpdate",
    "ToneSelectionCreate",
    "ToneSelectionResponse",
    # Metrics API schemas
    "MetricsAverages",
    "SegmentComparisonItem",
    "SegmentMetricsResponse",
    "ShootoutComparisonResponse",
    "ShootoutMetadataResponse",
    "SignalChainSchema",
]
