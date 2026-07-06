"""BaseConsumer exposes the in-flight message to handlers and clears it after."""

from __future__ import annotations

import pytest

from messaging.consumer_base import BaseConsumer
from messaging.message_bus import QueueMessage


class _RecordingBus:
    """Minimal in-memory MessageBus standing in for pgmq."""

    def __init__(self) -> None:
        self.archived: list[int] = []
        self.sent: list[tuple[str, dict]] = []

    async def send(self, queue_name, message):
        self.sent.append((queue_name, dict(message)))
        return 1

    async def read(self, queue_name, *, visibility_timeout, batch_size):
        return []

    async def archive(self, queue_name, msg_id):
        self.archived.append(msg_id)
        return True

    async def set_vt(self, queue_name, msg_id, visibility_timeout):
        return None

    async def create_queue(self, queue_name):
        return None

    async def drop_queue(self, queue_name):
        return None


class _ObservingConsumer(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(
            message_bus=_RecordingBus(),
            queue_name="audio_commands",
            dead_letter_queue="dead_letter",
        )
        self.seen_msg_ids: list[int | None] = []

    async def handle_message(self, envelope) -> None:
        self.seen_msg_ids.append(self.current_message.msg_id if self.current_message else None)


def _message(msg_id: int = 42) -> QueueMessage:
    return QueueMessage(
        msg_id=msg_id,
        read_ct=1,
        message={"message_type": "process_audio", "source_bc": "test", "payload": {}},
    )


@pytest.mark.asyncio
async def test_current_message_set_during_handling_and_cleared_after() -> None:
    consumer = _ObservingConsumer()

    await consumer.process_message(_message(msg_id=42))

    assert consumer.seen_msg_ids == [42], "handler must see the in-flight message"
    assert consumer.current_message is None, "the message must be cleared after processing"


@pytest.mark.asyncio
async def test_current_message_cleared_after_handler_failure() -> None:
    class _FailingConsumer(_ObservingConsumer):
        async def handle_message(self, envelope) -> None:
            raise RuntimeError("boom")

    consumer = _FailingConsumer()
    consumer.max_retries = 0

    await consumer.process_message(_message(msg_id=7))

    assert consumer.current_message is None
