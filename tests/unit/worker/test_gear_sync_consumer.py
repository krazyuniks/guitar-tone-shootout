"""Unit tests for GearSyncConsumer compatibility shim.

The shim in worker.consumers.gear_sync delegates to T3kSyncGearSyncConsumer
(BaseConsumer subclass). Tests verify:
1. Constructor wires delegate with correct queue and retry config
2. poll_pack_queue and poll_model_queue call _poll_queue_once correctly
3. _poll_queue_once reads messages and delegates to process_message
4. _poll_queue_once catches all exceptions without propagation
5. _poll_queue_once restores delegate.queue_name in the finally block

Note: DLQ behaviour, retry semantics, and SQL safety are all tested via
BaseConsumer in tests/unit/core/test_messaging.py. These tests focus only
on the shim's delegation contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from worker.consumers.gear_sync import GearSyncConsumer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Async call tracker (replaces AsyncMock)
# ---------------------------------------------------------------------------


class AsyncTracker:
    """Async callable that records calls and optionally raises or returns a value."""

    def __init__(self, *, return_value=None, side_effect=None):
        self.calls: list[tuple] = []
        self.kwargs_calls: list[dict] = []
        self._result = return_value
        self._error = side_effect

    async def __call__(self, *args, **kwargs):
        self.calls.append(args)
        self.kwargs_calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def was_called(self) -> bool:
        return len(self.calls) > 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def consumer(
    session: AsyncSession,
    t3k_session: AsyncSession,
) -> GearSyncConsumer:
    return GearSyncConsumer(
        core_session=session,
        t3k_session=t3k_session,
        pack_queue_name="gear_sync",
        model_queue_name="gear_sync",
        dead_letter_queue="gear_sync_dlq",
    )


@pytest.fixture
def consumer_distinct_queues(
    session: AsyncSession,
    t3k_session: AsyncSession,
) -> GearSyncConsumer:
    return GearSyncConsumer(
        core_session=session,
        t3k_session=t3k_session,
        pack_queue_name="gear_sync",
        model_queue_name="gear_model_sync",
        dead_letter_queue="gear_sync_dlq",
    )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestGearSyncConsumerInit:
    """Shim constructor correctly wires delegate configuration."""

    def test_delegate_gets_pack_queue_name(self, consumer: GearSyncConsumer) -> None:
        """Delegate queue_name is set to pack_queue_name."""
        assert consumer._delegate.queue_name == "gear_sync"

    def test_delegate_gets_dead_letter_queue(self, consumer: GearSyncConsumer) -> None:
        """Delegate dead_letter_queue is set from constructor arg."""
        assert consumer._delegate.dead_letter_queue == "gear_sync_dlq"

    def test_delegate_gets_default_max_retries(self, consumer: GearSyncConsumer) -> None:
        """Delegate max_retries defaults to 5."""
        assert consumer._delegate.max_retries == 5

    def test_delegate_gets_custom_max_retries(
        self,
        session: AsyncSession,
        t3k_session: AsyncSession,
    ) -> None:
        """Delegate max_retries is set from constructor arg."""
        c = GearSyncConsumer(
            core_session=session,
            t3k_session=t3k_session,
            pack_queue_name="gear_sync",
            model_queue_name="gear_sync",
            dead_letter_queue="gear_sync_dlq",
            max_retries=3,
        )
        assert c._delegate.max_retries == 3

    def test_pack_and_model_queue_names_stored(self, consumer: GearSyncConsumer) -> None:
        """pack_queue_name and model_queue_name are stored on shim."""
        assert consumer.pack_queue_name == "gear_sync"
        assert consumer.model_queue_name == "gear_sync"


# ---------------------------------------------------------------------------
# poll_pack_queue and poll_model_queue delegation
# ---------------------------------------------------------------------------


class TestQueuePolling:
    """poll_pack_queue and poll_model_queue call _poll_queue_once correctly."""

    async def test_poll_pack_queue_calls_poll_once(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """poll_pack_queue delegates to _poll_queue_once(pack_queue_name)."""
        tracker = AsyncTracker()
        monkeypatch.setattr(consumer, "_poll_queue_once", tracker)
        await consumer.poll_pack_queue()
        assert tracker.was_called
        assert tracker.calls[0] == ("gear_sync",)

    async def test_poll_model_queue_skips_when_same_as_pack(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """poll_model_queue is a no-op when model queue == pack queue."""
        tracker = AsyncTracker()
        monkeypatch.setattr(consumer, "_poll_queue_once", tracker)
        await consumer.poll_model_queue()
        assert not tracker.was_called

    async def test_poll_model_queue_calls_poll_once_when_distinct(
        self,
        consumer_distinct_queues: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """poll_model_queue delegates to _poll_queue_once(model_queue_name) when distinct."""
        tracker = AsyncTracker()
        monkeypatch.setattr(consumer_distinct_queues, "_poll_queue_once", tracker)
        await consumer_distinct_queues.poll_model_queue()
        assert tracker.was_called
        assert tracker.calls[0] == ("gear_model_sync",)


# ---------------------------------------------------------------------------
# _poll_queue_once behaviour
# ---------------------------------------------------------------------------


class TestPollQueueOnce:
    """_poll_queue_once reads and processes messages via the delegate."""

    async def test_reads_messages_via_delegate_message_bus(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_poll_queue_once calls delegate.message_bus.read() with the queue name."""
        read_tracker = AsyncTracker(return_value=[])
        monkeypatch.setattr(consumer._delegate.message_bus, "read", read_tracker)
        await consumer._poll_queue_once("gear_sync")
        assert read_tracker.was_called
        assert read_tracker.calls[0][0] == "gear_sync"

    async def test_processes_each_message_via_delegate(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_poll_queue_once processes each message via delegate.process_message."""
        fake_messages = [object(), object()]
        read_tracker = AsyncTracker(return_value=fake_messages)
        process_tracker = AsyncTracker()
        monkeypatch.setattr(consumer._delegate.message_bus, "read", read_tracker)
        monkeypatch.setattr(consumer._delegate, "process_message", process_tracker)
        await consumer._poll_queue_once("gear_sync")
        assert process_tracker.call_count == 2

    async def test_catches_exceptions_without_propagating(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_poll_queue_once swallows all exceptions so the caller loop continues."""
        read_tracker = AsyncTracker(side_effect=RuntimeError("simulated poll error"))
        monkeypatch.setattr(consumer._delegate.message_bus, "read", read_tracker)
        # Should NOT raise — exceptions are caught internally
        await consumer._poll_queue_once("gear_sync")

    async def test_restores_delegate_queue_name_after_success(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """delegate.queue_name is restored to its original value after polling."""
        original = consumer._delegate.queue_name
        monkeypatch.setattr(
            consumer._delegate.message_bus,
            "read",
            AsyncTracker(return_value=[]),
        )
        await consumer._poll_queue_once("some_other_queue")
        assert consumer._delegate.queue_name == original

    async def test_restores_delegate_queue_name_after_error(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """delegate.queue_name is restored even when read raises."""
        original = consumer._delegate.queue_name
        monkeypatch.setattr(
            consumer._delegate.message_bus,
            "read",
            AsyncTracker(side_effect=RuntimeError("boom")),
        )
        await consumer._poll_queue_once("some_other_queue")
        assert consumer._delegate.queue_name == original
