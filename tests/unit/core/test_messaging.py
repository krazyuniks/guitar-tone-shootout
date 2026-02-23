"""Unit tests for core messaging contracts and base consumer behaviour."""

from __future__ import annotations

import asyncio
import json
import signal
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic import ValidationError

from messaging.commands import ProcessAudioCommand
from messaging.consumer_base import BaseConsumer
from messaging.envelope import MessageEnvelope
from messaging.events import VideoRenderedEvent
from messaging.message_bus import MessageEnvelopeLike, QueueMessage
from messaging.pgmq_client import PgmqClient

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class InMemoryMessageBus:
    """Simple in-memory message bus for unit testing."""

    def __init__(self, read_batches: list[list[QueueMessage]] | None = None) -> None:
        self._read_batches: deque[list[QueueMessage]] = deque(read_batches or [])
        self.read_requests: list[tuple[str, int, int]] = []
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.archived: list[tuple[str, int]] = []
        self.created: list[str] = []
        self.dropped: list[str] = []

    async def send(
        self,
        queue_name: str,
        message: dict[str, Any] | MessageEnvelopeLike,
    ) -> int:
        payload = (
            message.model_dump(mode="python")
            if isinstance(message, MessageEnvelopeLike)
            else message
        )
        self.sent.append((queue_name, payload))
        return len(self.sent)

    async def read(
        self,
        queue_name: str,
        *,
        visibility_timeout: int,
        batch_size: int,
    ) -> list[QueueMessage]:
        self.read_requests.append((queue_name, visibility_timeout, batch_size))
        if self._read_batches:
            return self._read_batches.popleft()
        return []

    async def archive(self, queue_name: str, msg_id: int) -> bool:
        self.archived.append((queue_name, msg_id))
        return True

    async def create_queue(self, queue_name: str) -> None:
        self.created.append(queue_name)

    async def drop_queue(self, queue_name: str) -> None:
        self.dropped.append(queue_name)


class RecordingConsumer(BaseConsumer):
    """Consumer test double with controllable transient failures."""

    def __init__(
        self,
        *,
        message_bus: InMemoryMessageBus,
        queue_name: str,
        dead_letter_queue: str,
        sleep_func: Callable[[float], Awaitable[None]],
        max_retries: int = 3,
        failures_before_success: int = 0,
    ) -> None:
        super().__init__(
            message_bus=message_bus,
            queue_name=queue_name,
            dead_letter_queue=dead_letter_queue,
            max_retries=max_retries,
            sleep_func=sleep_func,
            poll_interval_seconds=0.01,
        )
        self.failures_before_success = failures_before_success
        self.handled: list[MessageEnvelope] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.reset_count = 0

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        self.handled.append(envelope)
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("transient failure")

    async def commit_message(self) -> None:
        self.commit_count += 1

    async def rollback_message(self) -> None:
        self.rollback_count += 1

    async def reset_message_context(self) -> None:
        self.reset_count += 1


class ProcessingFailureConsumer(RecordingConsumer):
    """Consumer that simulates processing-path write failures in run()."""

    async def process_message(self, _queued_message: QueueMessage) -> None:
        raise RuntimeError("simulated archive failure")

    def _register_signal_handlers(self) -> None:
        """No-op for deterministic unit tests."""
        return None


class ScalarOneResult:
    """Minimal result object for pgmq scalar queries in tests."""

    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class RecordingSession:
    """Async session stub that records SQL params for assertions."""

    def __init__(self) -> None:
        self.execute_calls: list[dict[str, Any]] = []

    async def execute(self, _stmt: object, params: dict[str, Any]) -> ScalarOneResult:
        self.execute_calls.append(params)
        return ScalarOneResult(77)


class MappedResult:
    """Result stub that emulates SQLAlchemy mappings().all() access."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> MappedResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class ReadRecordingSession:
    """Async session stub for pgmq read() success path assertions."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.execute_calls: list[dict[str, Any]] = []
        self.rollback_count = 0

    async def execute(self, _stmt: object, params: dict[str, Any]) -> MappedResult:
        self.execute_calls.append(params)
        return MappedResult(self._rows)

    async def rollback(self) -> None:
        self.rollback_count += 1


class FailingReadSession:
    """Async session stub for pgmq read() rollback/error path assertions."""

    def __init__(self) -> None:
        self.rollback_count = 0

    async def execute(self, _stmt: object, _params: dict[str, Any]) -> MappedResult:
        raise RuntimeError("simulated read failure")

    async def rollback(self) -> None:
        self.rollback_count += 1


class FakeSignalLoop:
    """Loop stub that can fail one signal registration and track attempts."""

    def __init__(self) -> None:
        self.registered_signals: list[signal.Signals] = []

    def add_signal_handler(self, sig: int, _callback: object) -> None:
        signal_value = signal.Signals(sig)
        self.registered_signals.append(signal_value)
        if signal_value is signal.SIGINT:
            raise RuntimeError("simulated signal registration failure")


def _build_process_audio_message() -> dict[str, Any]:
    """Create a valid command envelope payload."""
    return ProcessAudioCommand(
        source_bc="webapp",
        payload={
            "job_id": str(uuid.uuid7()),
            "shootout_id": str(uuid.uuid7()),
            "user_id": str(uuid.uuid7()),
        },
    ).model_dump(mode="python")


def test_message_envelope_round_trip_serialization() -> None:
    """Envelope should serialize and validate back to the same values."""
    envelope = MessageEnvelope(
        message_type="custom.command",
        source_bc="webapp",
        correlation_id=uuid.uuid7(),
        payload={"key": "value"},
    )

    restored = MessageEnvelope.model_validate(envelope.model_dump(mode="json"))

    assert restored == envelope
    assert restored.message_id.version == 7
    assert restored.timestamp.tzinfo is not None


def test_process_audio_command_payload_validation() -> None:
    """Commands should enforce typed payload shape."""
    command = ProcessAudioCommand(
        source_bc="webapp",
        payload={
            "job_id": str(uuid.uuid7()),
            "shootout_id": str(uuid.uuid7()),
            "user_id": str(uuid.uuid7()),
        },
    )

    assert command.message_type == "process_audio"

    with pytest.raises(ValidationError):
        ProcessAudioCommand(
            source_bc="webapp",
            payload={
                "job_id": str(uuid.uuid7()),
            },
        )


def test_video_rendered_event_enforces_literal_message_type() -> None:
    """Events should reject payloads with incorrect message_type literals."""
    with pytest.raises(ValidationError):
        VideoRenderedEvent(
            message_type="audio_processed",
            source_bc="video-worker",
            payload={
                "job_id": str(uuid.uuid7()),
                "shootout_id": str(uuid.uuid7()),
                "video_id": str(uuid.uuid7()),
            },
        )


@pytest.mark.asyncio
async def test_pgmq_client_send_serializes_python_mode_envelope_dump() -> None:
    """pgmq send should serialize UUID/datetime values from Python-mode dumps."""
    session = RecordingSession()
    client = PgmqClient(cast("Any", session))
    envelope_payload = ProcessAudioCommand(
        source_bc="webapp",
        payload={
            "job_id": str(uuid.uuid7()),
            "shootout_id": str(uuid.uuid7()),
            "user_id": str(uuid.uuid7()),
        },
    ).model_dump(mode="python")

    msg_id = await client.send("process_audio", envelope_payload)

    assert msg_id == 77
    assert len(session.execute_calls) == 1
    serialized_message = session.execute_calls[0]["message"]
    decoded_message = json.loads(serialized_message)
    assert decoded_message["message_type"] == "process_audio"
    assert isinstance(decoded_message["message_id"], str)
    assert isinstance(decoded_message["timestamp"], str)


@pytest.mark.asyncio
async def test_pgmq_client_send_accepts_message_envelope_instance() -> None:
    """pgmq send should dispatch through MessageEnvelopeLike model_dump path."""
    session = RecordingSession()
    client = PgmqClient(cast("Any", session))
    envelope = MessageEnvelope(
        message_type="custom.command",
        source_bc="webapp",
        correlation_id=uuid.uuid7(),
        payload={"job_id": str(uuid.uuid7())},
    )

    msg_id = await client.send("process_audio", envelope)

    assert msg_id == 77
    assert len(session.execute_calls) == 1
    serialized_message = session.execute_calls[0]["message"]
    decoded_message = json.loads(serialized_message)
    assert decoded_message["message_type"] == "custom.command"
    assert decoded_message["payload"]["job_id"] == envelope.payload["job_id"]
    assert isinstance(decoded_message["message_id"], str)
    assert isinstance(decoded_message["timestamp"], str)


@pytest.mark.asyncio
async def test_pgmq_client_read_maps_rows_to_queue_messages() -> None:
    """pgmq read should map row fields into QueueMessage objects."""
    now = datetime.now(UTC)
    session = ReadRecordingSession(
        rows=[
            {
                "msg_id": 41,
                "read_ct": 2,
                "message": _build_process_audio_message(),
                "enqueued_at": now,
                "vt": now,
            },
        ],
    )
    client = PgmqClient(cast("Any", session), max_poll_seconds=3, poll_interval_ms=250)

    messages = await client.read("process_audio", visibility_timeout=90, batch_size=5)

    assert len(messages) == 1
    message = messages[0]
    assert message.msg_id == 41
    assert message.read_ct == 2
    assert message.message["message_type"] == "process_audio"
    assert message.enqueued_at == now
    assert message.vt == now
    assert session.execute_calls == [
        {
            "queue": "process_audio",
            "vt": 90,
            "qty": 5,
            "max_poll_seconds": 3,
            "poll_interval_ms": 250,
        },
    ]
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_pgmq_client_read_rolls_back_and_reraises_when_execute_fails() -> None:
    """pgmq read should rollback failed transactions so polling can continue."""
    session = FailingReadSession()
    client = PgmqClient(cast("Any", session))

    with pytest.raises(RuntimeError, match="simulated read failure"):
        await client.read("process_audio", visibility_timeout=60, batch_size=10)

    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_register_signal_handlers_attempts_both_signals_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure on SIGINT must not prevent SIGTERM registration."""
    bus = InMemoryMessageBus()

    async def noop_sleep(_: float) -> None:
        return None

    consumer = RecordingConsumer(
        message_bus=bus,
        queue_name="process_audio",
        dead_letter_queue="process_audio_dlq",
        sleep_func=noop_sleep,
    )
    fake_loop = FakeSignalLoop()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    consumer._register_signal_handlers()

    assert fake_loop.registered_signals == [signal.SIGINT, signal.SIGTERM]


@pytest.mark.asyncio
async def test_consumer_retries_with_exponential_backoff() -> None:
    """Transient failures should back off and succeed on a later delivery."""
    bus = InMemoryMessageBus()
    sleep_calls: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    consumer = RecordingConsumer(
        message_bus=bus,
        queue_name="process_audio",
        dead_letter_queue="process_audio_dlq",
        sleep_func=record_sleep,
        failures_before_success=1,
    )
    message = _build_process_audio_message()

    await consumer.process_message(QueueMessage(msg_id=10, read_ct=1, message=message))

    assert sleep_calls == [1.0]
    assert bus.archived == []
    assert bus.sent == []
    assert consumer.rollback_count == 1
    assert consumer.commit_count == 0
    assert consumer.reset_count == 1

    await consumer.process_message(QueueMessage(msg_id=10, read_ct=2, message=message))

    assert bus.archived == [("process_audio", 10)]
    assert len(consumer.handled) == 2
    assert consumer.rollback_count == 1
    assert consumer.commit_count == 1
    assert consumer.reset_count == 2


@pytest.mark.asyncio
async def test_consumer_run_handles_process_message_exceptions_without_crashing() -> None:
    """run() should catch processing exceptions, back off, and continue loop control."""
    message = _build_process_audio_message()
    bus = InMemoryMessageBus(
        read_batches=[
            [QueueMessage(msg_id=22, read_ct=1, message=message)],
        ],
    )
    sleep_calls: list[float] = []
    consumer: ProcessingFailureConsumer | None = None

    async def stop_after_first_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if consumer is not None:
            consumer.request_shutdown()

    consumer = ProcessingFailureConsumer(
        message_bus=bus,
        queue_name="process_audio",
        dead_letter_queue="process_audio_dlq",
        sleep_func=stop_after_first_sleep,
    )

    await consumer.run()

    assert sleep_calls == [1.0]
    assert bus.archived == []
    assert bus.sent == []


@pytest.mark.asyncio
async def test_consumer_routes_to_dlq_after_final_retry_failure() -> None:
    """Final allowed retry failure should dead-letter and archive the message."""
    bus = InMemoryMessageBus()
    sleep_calls: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    consumer = RecordingConsumer(
        message_bus=bus,
        queue_name="process_audio",
        dead_letter_queue="process_audio_dlq",
        sleep_func=record_sleep,
        max_retries=3,
        failures_before_success=1,
    )
    message = _build_process_audio_message()

    await consumer.process_message(QueueMessage(msg_id=20, read_ct=4, message=message))

    assert sleep_calls == []
    assert bus.archived == [("process_audio", 20)]
    assert len(bus.sent) == 1
    assert bus.sent[0][0] == "process_audio_dlq"
    assert bus.sent[0][1]["failed_msg_id"] == 20
    assert bus.sent[0][1]["failed_read_count"] == 4
    assert bus.sent[0][1]["message"]["message_type"] == "process_audio"
    assert len(consumer.handled) == 1
    assert consumer.rollback_count == 1
    assert consumer.commit_count == 1
    assert consumer.reset_count == 2


@pytest.mark.asyncio
async def test_consumer_routes_to_dlq_when_retry_budget_is_already_exceeded() -> None:
    """Messages already beyond retry budget should skip processing and dead-letter."""
    bus = InMemoryMessageBus()

    async def noop_sleep(_: float) -> None:
        return None

    consumer = RecordingConsumer(
        message_bus=bus,
        queue_name="process_audio",
        dead_letter_queue="process_audio_dlq",
        sleep_func=noop_sleep,
        max_retries=3,
    )
    message = _build_process_audio_message()

    await consumer.process_message(QueueMessage(msg_id=21, read_ct=5, message=message))

    assert bus.archived == [("process_audio", 21)]
    assert len(bus.sent) == 1
    assert bus.sent[0][0] == "process_audio_dlq"
    assert bus.sent[0][1]["failed_msg_id"] == 21
    assert bus.sent[0][1]["failed_read_count"] == 5
    assert bus.sent[0][1]["message"]["message_type"] == "process_audio"
    assert consumer.rollback_count == 1
    assert consumer.commit_count == 1
    assert consumer.reset_count == 2
