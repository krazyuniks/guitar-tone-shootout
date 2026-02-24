"""Gear sync pgmq consumer for the T3K sync container."""

from __future__ import annotations

from gts.records.gear_sync import GearSyncRecord
from messaging.consumer_base import BaseConsumer
from messaging.envelope import MessageEnvelope
from messaging.pgmq_client import PgmqClient
from worker.services.gear_mapper import GearMapperService


class GearSyncConsumer(BaseConsumer):
    """Consume gear_sync messages and map them into unified core gear records."""

    def __init__(self, session) -> None:
        super().__init__(
            message_bus=PgmqClient(session),
            queue_name="gear_sync",
            dead_letter_queue="gear_sync_dlq",
            poll_interval_seconds=5.0,
            max_retries=5,
        )
        self._session = session
        self._mapper = GearMapperService(session=session)

    def parse_message(self, message: dict[str, object]) -> MessageEnvelope:
        """Convert deterministic gear_sync records into a standard envelope."""
        record = GearSyncRecord.from_dict(message)
        return MessageEnvelope(
            message_type="gear_sync",
            source_bc=record.source_name,
            payload=record.to_dict(),
        )

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Apply one gear sync record."""
        record = GearSyncRecord.from_dict(envelope.payload)
        await self._mapper.process_sync_record(record)

    async def commit_message(self) -> None:
        """Commit mapped domain writes and queue archive together."""
        await self._session.commit()

    async def rollback_message(self) -> None:
        """Rollback failed message attempts before retry/DLQ decisions."""
        await self._session.rollback()

    async def reset_message_context(self) -> None:
        """Clear session identity state between long-lived message iterations."""
        self._session.expunge_all()


T3KConsumer = GearSyncConsumer
