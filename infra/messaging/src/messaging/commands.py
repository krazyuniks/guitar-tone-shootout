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


class StartShootoutCommand(MessageEnvelope):
    """Command to start a shootout run: fan out per-chain audio jobs."""

    message_type: Literal["start_shootout"] = "start_shootout"
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _validate_payload_shape(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Require the parent SHOOTOUT job id the orchestrator loads."""
        if "job_id" not in value:
            raise ValueError("payload missing required keys: job_id")
        return value


class FinaliseShootoutCommand(MessageEnvelope):
    """Command to publish a completed shootout render as a manifest."""

    message_type: Literal["finalise_shootout"] = "finalise_shootout"
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _validate_payload_shape(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Require the SHOOTOUT_FINALISE job id the orchestrator loads."""
        if "job_id" not in value:
            raise ValueError("payload missing required keys: job_id")
        return value


class SyncGearCommand(MessageEnvelope):
    """Command to trigger source synchronization."""

    message_type: Literal["sync_gear"] = "sync_gear"
    payload: dict[str, Any]
