"""Pydantic schemas for Job API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    """Response schema for a job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    job_type: Literal[
        "audio_processing",
        "video_compose",
        "gear_sync",
        "model_download",
        "ir_download",
        "notification",
    ]
    status: Literal[
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        "dead_lettered",
    ]
    progress: int
    message: str | None = None
    error: str | None = None
    result_path: str | None = None
    entity_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
