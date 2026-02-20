"""Event message schemas emitted by bounded contexts."""

from __future__ import annotations

from typing import Any, Literal

from core.records.envelope import MessageEnvelope


class GearSyncedEvent(MessageEnvelope):
    """Event emitted when source sync completes."""

    message_type: Literal["gear_synced"] = "gear_synced"
    payload: dict[str, Any]


class AudioProcessedEvent(MessageEnvelope):
    """Event emitted when audio processing completes."""

    message_type: Literal["audio_processed"] = "audio_processed"
    payload: dict[str, Any]


class VideoRenderedEvent(MessageEnvelope):
    """Event emitted when video rendering completes."""

    message_type: Literal["video_rendered"] = "video_rendered"
    payload: dict[str, Any]
