"""Pydantic schemas for Worker Admin API endpoints."""

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
    task_id: str | None
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


class SyncCheckpointInfo(BaseModel):
    """Checkpoint information for sync status."""

    last_tone_id: str | None = None
    last_model_id: str | None = None


class SyncStatusResponse(BaseModel):
    """Response for sync status endpoint."""

    status: str  # "running" or "idle"
    enabled: bool
    checkpoint: SyncCheckpointInfo | None = None


class SyncTriggerResponse(BaseModel):
    """Response for sync trigger endpoint."""

    message: str


class SyncStatsResponse(BaseModel):
    """Response for sync stats endpoint."""

    total_synced: int
    last_sync_duration: float | None = None
    queue_depths: dict[str, int] = Field(default_factory=dict)


class SyncLagResponse(BaseModel):
    """Response for sync lag endpoint."""

    lag_seconds: float | None = None


class ErrorsSummaryResponse(BaseModel):
    """Response for errors summary endpoint."""

    errors: dict[str, int] = Field(default_factory=dict)
    time_window_hours: int


class PendingRetriesCountResponse(BaseModel):
    """Response for pending retries count endpoint."""

    count: int


class UnlockResponse(BaseModel):
    """Response for unlock endpoints."""

    message: str


class APICallWindowMetrics(BaseModel):
    """Metrics for a single time window."""

    window_seconds: int
    successful: int
    failed: int
    avg_success_per_minute: float
    avg_failure_per_minute: float


class APIStatsResponse(BaseModel):
    """Response for API stats endpoint."""

    windows: list[APICallWindowMetrics]


class TokenRefreshRequest(BaseModel):
    """Request to refresh T3K OAuth token."""

    auth_file_path: str
    base_url: str
    encryption_key: str


class TokenRefreshResponse(BaseModel):
    """Response from token refresh endpoint."""

    auth_status: str
    message: str
