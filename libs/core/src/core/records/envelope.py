"""Message envelope contract shared by all bounded contexts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _new_message_id() -> uuid.UUID:
    """Generate UUIDv7 IDs for time-ordered message tracing."""
    return uuid.uuid7()


def _utc_now() -> datetime:
    """Get a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class MessageEnvelope(BaseModel):
    """Base message envelope for commands and events."""

    model_config = ConfigDict(extra="forbid")

    message_id: uuid.UUID = Field(default_factory=_new_message_id)
    message_type: str = Field(min_length=1)
    source_bc: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=_utc_now)
    correlation_id: uuid.UUID | None = None
    payload: dict[str, Any]

    @field_validator("message_id")
    @classmethod
    def _validate_message_id(cls, value: uuid.UUID) -> uuid.UUID:
        """Require UUIDv7 IDs for envelope ordering semantics."""
        if value.version != 7:
            raise ValueError("message_id must be a UUIDv7 value")
        return value

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, value: datetime) -> datetime:
        """Ensure the timestamp is always timezone-aware UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
