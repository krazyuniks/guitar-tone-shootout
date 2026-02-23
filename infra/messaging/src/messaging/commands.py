"""Command message schemas for cross-BC orchestration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import field_validator

from messaging.envelope import MessageEnvelope


class ProcessAudioCommand(MessageEnvelope):
    """Command to trigger audio processing."""

    message_type: Literal["process_audio"] = "process_audio"
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _validate_payload_shape(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Require job context IDs for deterministic audio processing."""
        required_keys = {"job_id", "shootout_id", "user_id"}
        missing_keys = sorted(required_keys - value.keys())
        if missing_keys:
            raise ValueError(f"payload missing required keys: {', '.join(missing_keys)}")
        return value


class RenderVideoCommand(MessageEnvelope):
    """Command to trigger video rendering."""

    message_type: Literal["render_video"] = "render_video"
    payload: dict[str, Any]


class SyncGearCommand(MessageEnvelope):
    """Command to trigger source synchronization."""

    message_type: Literal["sync_gear"] = "sync_gear"
    payload: dict[str, Any]
