"""Pydantic schemas for Job API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from gts.domain.value_objects.job_status import JobStatus, JobType


class JobResponse(BaseModel):
    """Response schema for a job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    job_type: JobType
    status: JobStatus
    progress: int
    message: str | None = None
    error: str | None = None
    entity_id: UUID | None = None
    parent_job_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    children: list[JobResponse] = Field(default_factory=list)
