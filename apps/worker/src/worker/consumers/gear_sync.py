"""GearSyncConsumer for polling pgmq queues and processing gear sync records."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from core.records.gear_sync import GearSyncRecord
from worker.services.gear_mapper import GearMapperService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GearSyncConsumer:
    """Consumer for gear pack and model sync queues.

    Polls pgmq queues in gts_t3k_source database and processes messages
    by deserializing to GearSyncRecord and delegating to GearMapperService.
    """

    def __init__(
        self,
        core_session: AsyncSession,
        t3k_session: AsyncSession,
        pack_queue_name: str,
        model_queue_name: str,
        dead_letter_queue: str,
    ) -> None:
        self.core_session = core_session
        self.t3k_session = t3k_session
        self.pack_queue_name = pack_queue_name
        self.model_queue_name = model_queue_name
        self.dead_letter_queue = dead_letter_queue
        self.mapper = GearMapperService(session=core_session)

    async def poll_pack_queue(self) -> None:
        """Poll the pack sync queue and process messages."""
        messages = await self._poll_queue(self.pack_queue_name)

        for message in messages:
            try:
                if message.read_ct > 5:
                    await self._dead_letter(message, self.pack_queue_name)
                    continue

                record = GearSyncRecord.from_dict(message.message)
                await self.mapper.process_pack_sync(record)
                await self._archive_message(self.pack_queue_name, message.msg_id)

            except Exception:
                logger.exception("Error processing pack message %s", message.msg_id)
                await self._dead_letter(message, self.pack_queue_name)

    async def poll_model_queue(self) -> None:
        """Poll the model sync queue and process messages."""
        messages = await self._poll_queue(self.model_queue_name)

        for message in messages:
            try:
                if message.read_ct > 5:
                    await self._dead_letter(message, self.model_queue_name)
                    continue

                record = GearSyncRecord.from_dict(message.message)
                await self.mapper.process_model_sync(record)
                await self._archive_message(self.model_queue_name, message.msg_id)

            except Exception:
                logger.exception("Error processing model message %s", message.msg_id)
                await self._dead_letter(message, self.model_queue_name)

    async def _poll_queue(self, queue_name: str) -> list:
        """Poll a pgmq queue for messages."""
        try:
            stmt = text("SELECT * FROM pgmq.read_with_poll(:queue, :vt, :qty)")
            result = await self.t3k_session.execute(
                stmt,
                queue=queue_name,
                vt=60,
                qty=10,
            )
            return result.fetchall()
        except Exception:
            logger.exception("Error polling queue %s", queue_name)
            return []

    async def _archive_message(self, queue_name: str, msg_id: int) -> None:
        """Archive a successfully processed message."""
        stmt = text("SELECT pgmq.archive(:queue, :msg_id)")
        await self.t3k_session.execute(
            stmt,
            queue=queue_name,
            msg_id=msg_id,
        )

    async def _dead_letter(self, message: object, queue_name: str) -> None:
        """Move a message to the dead letter queue."""
        msg_data = message.message
        if isinstance(msg_data, dict):
            msg_data = json.dumps(msg_data)
        stmt = text(f"SELECT pgmq.send('{self.dead_letter_queue}', :message::jsonb)")
        await self.t3k_session.execute(
            stmt,
            message=msg_data,
        )
        await self._archive_message(queue_name, message.msg_id)

    async def run(self) -> None:
        """Main polling loop."""
        while True:
            await self.poll_pack_queue()
            await self.poll_model_queue()
            await asyncio.sleep(5)
