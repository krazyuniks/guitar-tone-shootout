"""Pydantic schemas for Admin API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from gts.domain.value_objects.job_status import JobStatus, JobType


class JobSummary(BaseModel):
    """Summary of a job for list endpoints."""

    id: UUID
    job_type: JobType
    status: JobStatus
    progress: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None
    user_id: UUID | None = None
    parent_job_id: UUID | None = None

    model_config = {"from_attributes": True}


class JobDetail(BaseModel):
    """Detailed job information including child jobs."""

    id: UUID
    user_id: UUID | None
    job_type: JobType
    parent_job_id: UUID | None
    status: JobStatus
    progress: int
    message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    last_heartbeat: datetime | None
    attempt: int
    max_attempts: int
    next_retry_at: datetime | None
    result_path: str | None
    error: str | None
    entity_id: UUID | None
    created_at: datetime
    updated_at: datetime
    children: list[JobSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EnqueueRequest(BaseModel):
    """Request body for enqueue endpoint."""

    job_id: UUID


class EnqueueResponse(BaseModel):
    """Response for enqueue endpoint."""

    id: UUID


class SyncTriggerResponse(BaseModel):
    """Response for sync trigger endpoint."""

    message: str


class ErrorsSummaryResponse(BaseModel):
    """Response for errors summary endpoint."""

    errors: dict[str, int] = Field(default_factory=dict)
    time_window_hours: int


class PendingRetriesCountResponse(BaseModel):
    """Response for pending retries count endpoint."""

    count: int


class QueueDepthResponse(BaseModel):
    """Current number of visible and in-flight messages in a queue."""

    depth: int


class UnlockResponse(BaseModel):
    """Response for unlock endpoints."""

    message: str
