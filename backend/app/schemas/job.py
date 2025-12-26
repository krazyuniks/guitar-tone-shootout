"""Job schemas for API request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.job import JobStatus


class JobCreate(BaseModel):
    """Request schema for creating a new job."""

    config: dict[str, object] = Field(
        description="Job configuration (models, DI track, etc.)",
        examples=[{"di_track": "track.wav", "models": ["model1", "model2"]}],
    )


class JobResponse(BaseModel):
    """Response schema for a single job."""

    id: UUID
    user_id: UUID
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str | None
    config: str | None
    started_at: datetime | None
    completed_at: datetime | None
    result_path: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Response schema for listing jobs."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobProgressUpdate(BaseModel):
    """Schema for job progress WebSocket updates."""

    type: str = "progress"
    job_id: UUID
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str | None
    timestamp: datetime
