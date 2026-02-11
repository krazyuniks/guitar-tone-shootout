"""Pydantic schemas for Worker Admin API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from core.domain.value_objects.job_status import JobStatus, JobType


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
