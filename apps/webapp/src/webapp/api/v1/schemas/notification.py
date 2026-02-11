"""Pydantic schemas for Notification API endpoints."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """Response schema for a notification."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: str
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime


class MarkReadResponse(BaseModel):
    """Response schema for marking a notification as read."""

    success: bool


class MarkAllReadResponse(BaseModel):
    """Response schema for marking all notifications as read."""

    marked_count: int
