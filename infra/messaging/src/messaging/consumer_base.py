"""Base class for pgmq consumers with retries, DLQ handling, and shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from messaging.envelope import MessageEnvelope

#: Lease renewal cadence while a handler works a message. Contract invariant:
#: HEARTBEAT_INTERVAL_SECONDS * 2 < VT_EXTENSION_SECONDS < the transition
#: service's LEASE_THRESHOLD, so one missed beat never causes redelivery and a
#: crashed worker's message redelivers before the reaper declares it dead.
HEARTBEAT_INTERVAL_SECONDS = 20.0

#: Visibility window granted by each heartbeat's set_vt.
VT_EXTENSION_SECONDS = 90

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from messaging.message_bus import MessageBus, QueueMessage


class SkipMessage(Exception):
    """Raised by a handler to release a message without acknowledging it.

    The message stays invisible until its visibility timeout lapses, then
    redelivers. Used when another consumer holds a live lease on the job.
    """


class BaseConsumer(ABC):
    """Common polling loop and failure handling for pgmq consumers.

    Subclasses that use transactional resources (for example SQLAlchemy sessions)
    should override commit/rollback/reset hooks so domain writes and queue
    archive/dead-letter operations are finalized in deterministic boundaries.
    """

    def __init__(
        self,
        *,
        message_bus: MessageBus,
        queue_name: str,
        dead_letter_queue: str,
        visibility_timeout: int = 60,
        batch_size: int = 10,
        poll_interval_seconds: float = 1.0,
        max_retries: int = 3,
        max_backoff_seconds: float = 30.0,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.message_bus = message_bus
        self.queue_name = queue_name
        self.dead_letter_queue = dead_letter_queue
        self.visibility_timeout = visibility_timeout
        self.batch_size = batch_size
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries
        self.max_backoff_seconds = max_backoff_seconds
        self._sleep = sleep_func
        self._shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(self.__class__.__name__)
        #: The message currently being processed; handlers may read msg_id for
        #: lease renewal (set_vt) while their work runs.
        self.current_message: QueueMessage | None = None

    def request_shutdown(self) -> None:
        """Signal the consumer to stop after the current iteration."""
        self._shutdown_event.set()

    async def run(self) -> None:
        """Start the polling loop until shutdown is requested."""
        self._register_signal_handlers()
        consecutive_read_errors = 0
        consecutive_process_errors = 0

        while not self._shutdown_event.is_set():
            try:
                messages = await self.message_bus.read(
                    self.queue_name,
                    visibility_timeout=self.visibility_timeout,
                    batch_size=self.batch_size,
                )
                consecutive_read_errors = 0
            except Exception:
                consecutive_read_errors += 1
                delay = self._backoff_seconds(consecutive_read_errors)
                self.logger.exception("Failed to read from queue %s", self.queue_name)
                await self._sleep(delay)
                continue

            if not messages:
                await self._sleep(self.poll_interval_seconds)
                continue

            for message in messages:
                if self._shutdown_event.is_set():
                    return
                try:
                    await self.process_message(message)
                    consecutive_process_errors = 0
                except Exception:
                    consecutive_process_errors += 1
                    delay = self._backoff_seconds(consecutive_process_errors)
                    self.logger.exception(
                        "Failed to process message %s from queue %s",
                        message.msg_id,
                        self.queue_name,
                    )
                    await self._sleep(delay)

    async def process_message(self, queued_message: QueueMessage) -> None:
        """Process one queue message with retry and DLQ semantics."""
        self.current_message = queued_message
        try:
            await self._process_message_inner(queued_message)
        finally:
            self.current_message = None

    async def _process_message_inner(self, queued_message: QueueMessage) -> None:
        max_attempts = self.max_retries + 1
        current_attempt = queued_message.read_ct

        if current_attempt > max_attempts:
            await self.rollback_message()
            await self.reset_message_context()
            await self._move_to_dead_letter(
                queued_message,
                "max retries exceeded before processing",
            )
            await self.commit_message()
            await self.reset_message_context()
            return

        try:
            envelope = self.parse_message(queued_message.message)
        except ValidationError as error:
            await self.rollback_message()
            await self.reset_message_context()
            await self._move_to_dead_letter(queued_message, f"invalid envelope: {error}")
            await self.commit_message()
            await self.reset_message_context()
            return
        try:
            await self.handle_message(envelope)
            await self.message_bus.archive(self.queue_name, queued_message.msg_id)
            await self.commit_message()
            await self.reset_message_context()
            return
        except SkipMessage:
            # Release without acknowledging: no archive, no retry accounting.
            await self.rollback_message()
            await self.reset_message_context()
            self.logger.warning(
                "Released message %s from %s without ack (live lease elsewhere)",
                queued_message.msg_id,
                self.queue_name,
            )
            return
        except Exception as error:
            await self.rollback_message()
            await self.reset_message_context()
            if current_attempt >= max_attempts:
                await self._move_to_dead_letter(queued_message, f"processing failed: {error}")
                await self.commit_message()
                await self.reset_message_context()
                return

            delay = self._backoff_seconds(current_attempt)
            self.logger.warning(
                "Message %s failed on attempt %s/%s, retrying in %.2fs",
                queued_message.msg_id,
                current_attempt,
                max_attempts,
                delay,
            )
            await self._sleep(delay)
            return

    async def commit_message(self) -> None:
        """Commit transactional state after successful processing and archive."""
        return None

    async def rollback_message(self) -> None:
        """Rollback transactional state after a failed processing attempt."""
        return None

    async def reset_message_context(self) -> None:
        """Reset per-message context to avoid stale in-memory state."""
        return None

    @abstractmethod
    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Process a validated message envelope."""
        ...

    def parse_message(self, message: dict[str, object]) -> MessageEnvelope:
        """Parse a raw queue message into a standard envelope."""
        return MessageEnvelope.model_validate(message)

    async def _move_to_dead_letter(
        self,
        queued_message: QueueMessage,
        reason: str,
    ) -> None:
        """Publish message to DLQ and archive it from the main queue."""
        dlq_message = {
            "failed_queue": self.queue_name,
            "failed_msg_id": queued_message.msg_id,
            "failed_read_count": queued_message.read_ct,
            "failed_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "message": queued_message.message,
        }
        await self.message_bus.send(self.dead_letter_queue, dlq_message)
        await self.message_bus.archive(self.queue_name, queued_message.msg_id)
        await self.on_dead_letter(queued_message.message, reason)

    async def on_dead_letter(
        self,
        message: dict[str, object],  # noqa: ARG002 - hook signature for overrides
        reason: str,  # noqa: ARG002
    ) -> None:
        """Hook after a message is dead-lettered; runs in the same session.

        Job-backed consumers override this to mark their job row
        DEAD_LETTERED in the same commit as the DLQ write, so the queue-level
        and job-row views of "dead-lettered" can never diverge. Default no-op
        (messages without a job row, e.g. gear-sync events).
        """
        return None

    def _backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff capped by max_backoff_seconds."""
        bounded_attempt = max(attempt - 1, 0)
        return min(2.0**bounded_attempt, self.max_backoff_seconds)

    def _register_signal_handlers(self) -> None:
        """Install SIGINT/SIGTERM handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_shutdown)
            except (NotImplementedError, RuntimeError, ValueError):
                continue
