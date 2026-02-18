"""GearSyncConsumer for polling pgmq queues and processing gear sync records."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

from sqlalchemy import text

from core.records.gear_sync import GearSyncRecord
from worker.services.gear_mapper import GearMapperService, RetryableGearSyncError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GearSyncConsumer:
    """Consumer for gear pack and model sync queues.

    Polls pgmq queue(s) in gts_t3k_source database and processes messages
    by deserializing to GearSyncRecord and delegating to GearMapperService.

    Runtime is configured to use a single `gear_sync` queue carrying
    pack+model aggregate records. Legacy dual-queue configuration is still
    accepted to avoid breaking existing wiring/tests.
    """

    def __init__(
        self,
        core_session: AsyncSession,
        t3k_session: AsyncSession,
        pack_queue_name: str,
        model_queue_name: str | None,
        dead_letter_queue: str,
        max_retries: int = 5,
    ) -> None:
        self.core_session = core_session
        self.t3k_session = t3k_session
        self.pack_queue_name = pack_queue_name
        self.model_queue_name = model_queue_name or pack_queue_name
        self.dead_letter_queue = dead_letter_queue
        self.max_retries = max_retries
        self.mapper = GearMapperService(session=core_session)

    async def poll_pack_queue(self) -> None:
        """Poll the pack sync queue and process messages."""
        await self._poll_and_process(self.pack_queue_name)

    async def poll_model_queue(self) -> None:
        """Poll the model sync queue and process messages."""
        # When both queue names are identical we are in single-queue mode and
        # poll_pack_queue already handled all messages for this cycle.
        if self.model_queue_name == self.pack_queue_name:
            return
        await self._poll_and_process(self.model_queue_name)

    async def _poll_and_process(self, queue_name: str) -> None:
        """Poll one queue and process messages with explicit transaction boundaries."""
        messages = await self._poll_queue(queue_name)

        for message in messages:
            try:
                if message.read_ct > self.max_retries:
                    await self._dead_letter(message, queue_name)
                    await self.t3k_session.commit()
                    continue

                record = GearSyncRecord.from_dict(message.message)
                await self.mapper.process_sync_record(record)
                await self.core_session.commit()
                await self._archive_stale_dlq_for_record(record)
                await self._archive_message(queue_name, message.msg_id)
                await self.t3k_session.commit()
            except RetryableGearSyncError as e:
                await self.core_session.rollback()
                await self.t3k_session.rollback()
                # Log message only on early retries; full trace on final attempt
                if message.read_ct >= self.max_retries - 1:
                    logger.warning(
                        "Retryable sync error for message %s on queue %s (read_ct=%s/%s)",
                        message.msg_id,
                        queue_name,
                        message.read_ct,
                        self.max_retries,
                        exc_info=True,
                    )
                else:
                    logger.info(
                        "Retryable: message %s on %s (read_ct=%s/%s): %s",
                        message.msg_id,
                        queue_name,
                        message.read_ct,
                        self.max_retries,
                        e,
                    )
            except Exception:
                await self.core_session.rollback()
                logger.exception("Error processing sync message %s", message.msg_id)
                await self._dead_letter(message, queue_name)
                await self.t3k_session.commit()

    async def _archive_stale_dlq_for_record(self, record: GearSyncRecord) -> None:
        """Archive stale DLQ entries for a record that just processed successfully.

        When a newer re-publish succeeds, older DLQ entries for the same
        source record are no longer actionable and can be safely archived.
        """
        if not re.fullmatch(r"[A-Za-z0-9_]+", self.dead_letter_queue):
            logger.warning(
                "Skipping DLQ cleanup due to invalid queue name: %s", self.dead_letter_queue
            )
            return

        dlq_table = f"pgmq.q_{self.dead_letter_queue}"
        try:
            stmt = text(
                f"""
                SELECT msg_id
                FROM {dlq_table}
                WHERE (message->>'source_name') = :source_name
                  AND (message->>'source_record_id') = :source_record_id
                """
            )
            result = await self.t3k_session.execute(
                stmt,
                {
                    "source_name": record.source_name,
                    "source_record_id": record.source_record_id,
                },
            )
            msg_ids = [row[0] for row in result]
            if not msg_ids:
                return

            for msg_id in msg_ids:
                await self._archive_message(self.dead_letter_queue, msg_id)

            logger.info(
                "Archived %d stale DLQ messages for %s:%s",
                len(msg_ids),
                record.source_name,
                record.source_record_id,
            )
        except Exception:
            logger.exception(
                "Failed to cleanup stale DLQ messages for %s:%s",
                record.source_name,
                record.source_record_id,
            )

    async def _poll_queue(self, queue_name: str) -> list:
        """Poll a pgmq queue for messages."""
        try:
            stmt = text("SELECT * FROM pgmq.read_with_poll(:queue, :vt, :qty)")
            result = await self.t3k_session.execute(
                stmt,
                {"queue": queue_name, "vt": 60, "qty": 10},
            )
            return result.fetchall()
        except Exception:
            logger.exception("Error polling queue %s", queue_name)
            # Recover poisoned session state (e.g. PendingRollbackError) so
            # subsequent poll attempts can continue without process restart.
            try:
                await self.t3k_session.rollback()
            except Exception:
                logger.exception("Error rolling back after poll failure for queue %s", queue_name)
            return []

    async def _archive_message(self, queue_name: str, msg_id: int) -> None:
        """Archive a successfully processed message."""
        stmt = text("SELECT pgmq.archive(CAST(:queue AS text), CAST(:msg_id AS bigint))")
        await self.t3k_session.execute(
            stmt,
            {"queue": queue_name, "msg_id": msg_id},
        )

    async def _dead_letter(self, message: object, queue_name: str) -> None:
        """Move a message to the dead letter queue."""
        msg_data = message.message
        if isinstance(msg_data, dict):
            msg_data = json.dumps(msg_data)
        stmt = text("SELECT pgmq.send(:queue, CAST(:message AS jsonb))")
        await self.t3k_session.execute(
            stmt,
            {"queue": self.dead_letter_queue, "message": msg_data},
        )
        await self._archive_message(queue_name, message.msg_id)

    async def run(self) -> None:
        """Main polling loop."""
        while True:
            await self.poll_pack_queue()
            await self.poll_model_queue()
            await asyncio.sleep(5)
