"""Legacy GearSyncConsumer compatibility shim.

Sync queue processing moved to `t3k_sync.consumer.GearSyncConsumer`.
This class remains import-compatible for worker callers until Story 04 removes
the monolithic worker.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from t3k_sync.consumer import GearSyncConsumer as T3kSyncGearSyncConsumer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GearSyncConsumer:
    """Compatibility surface that delegates to the dedicated t3k-sync consumer."""

    def __init__(
        self,
        core_session: AsyncSession,
        t3k_session: AsyncSession,  # noqa: ARG002
        pack_queue_name: str,
        model_queue_name: str | None,
        dead_letter_queue: str,
        max_retries: int = 5,
    ) -> None:
        self.pack_queue_name = pack_queue_name
        self.model_queue_name = model_queue_name or pack_queue_name
        self.dead_letter_queue = dead_letter_queue

        self._delegate = T3kSyncGearSyncConsumer(core_session)
        self._delegate.queue_name = pack_queue_name
        self._delegate.dead_letter_queue = dead_letter_queue
        self._delegate.max_retries = max_retries

    async def poll_pack_queue(self) -> None:
        """Poll one pack queue batch via the shared base-consumer flow."""
        await self._poll_queue_once(self.pack_queue_name)

    async def poll_model_queue(self) -> None:
        """Poll one model queue batch when configured as a distinct queue."""
        if self.model_queue_name == self.pack_queue_name:
            return
        await self._poll_queue_once(self.model_queue_name)

    async def _poll_queue_once(self, queue_name: str) -> None:
        original_queue = self._delegate.queue_name
        self._delegate.queue_name = queue_name
        try:
            messages = await self._delegate.message_bus.read(
                queue_name,
                visibility_timeout=self._delegate.visibility_timeout,
                batch_size=self._delegate.batch_size,
            )
            for message in messages:
                await self._delegate.process_message(message)
        except Exception:
            logger.exception("Compatibility gear sync poll failed for queue %s", queue_name)
        finally:
            self._delegate.queue_name = original_queue

    async def run(self) -> None:
        """Run compatibility polling loop with the legacy dual-queue cadence."""
        while True:
            await self.poll_pack_queue()
            await self.poll_model_queue()
            await asyncio.sleep(self._delegate.poll_interval_seconds)
