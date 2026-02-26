"""Audio command consumer for the audio-worker container."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from messaging.commands import ProcessAudioCommand
from messaging.consumer_base import BaseConsumer
from messaging.pgmq_client import PgmqClient

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from messaging.envelope import MessageEnvelope


async def process_audio_job(job_id: UUID) -> None:
    """Process an AUDIO_PROCESSING job.

    Full implementation is introduced in the dedicated audio-worker story.
    """
    logger.info("Received process_audio command for job_id=%s", job_id)


class ProcessAudioConsumer(BaseConsumer):
    """Consume process_audio queue commands."""

    def __init__(self, session) -> None:
        super().__init__(
            message_bus=PgmqClient(session),
            queue_name="audio_commands",
            dead_letter_queue="dead_letter",
        )
        self._session = session

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Handle one process_audio command envelope."""
        command = ProcessAudioCommand.model_validate(envelope.model_dump(mode="python"))
        job_id = UUID(command.payload["job_id"])
        await process_audio_job(job_id)

    async def commit_message(self) -> None:
        """Commit domain writes and queue archive in one transaction."""
        await self._session.commit()

    async def rollback_message(self) -> None:
        """Rollback failed message attempts before retry/DLQ decisions."""
        await self._session.rollback()

    async def reset_message_context(self) -> None:
        """Clear session identity state between long-lived message iterations."""
        self._session.expunge_all()
