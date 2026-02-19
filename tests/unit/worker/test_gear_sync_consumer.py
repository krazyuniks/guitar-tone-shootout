"""Unit tests for GearSyncConsumer bug fixes and behaviour.

Tests verify:
1. _poll_queue passes params as dict (not kwargs) to session.execute()
2. _archive_message passes params as dict (not kwargs) to session.execute()
3. _dead_letter uses parameterised SQL (not f-string) for queue name
4. Consumer dead-letters messages with read_ct > 5
5. Consumer dead-letters messages that fail schema validation
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from worker.consumers.gear_sync import GearSyncConsumer
from worker.services.gear_mapper import RetryableGearSyncError

# ---------------------------------------------------------------------------
# Async call tracker (replaces AsyncMock)
# ---------------------------------------------------------------------------


class AsyncTracker:
    """Async callable that records calls and optionally raises or returns a value."""

    def __init__(self, *, return_value=None, side_effect=None):
        self.calls: list[tuple] = []
        self.kwargs_calls: list[dict] = []
        self.return_value = return_value
        self.side_effect = side_effect

    async def __call__(self, *args, **kwargs):
        self.calls.append(args)
        self.kwargs_calls.append(kwargs)
        if self.side_effect is not None:
            raise self.side_effect
        return self.return_value

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


# ---------------------------------------------------------------------------
# Source inspection helpers
# ---------------------------------------------------------------------------


def _get_method_source(method_name: str) -> str:
    """Get the source code of a GearSyncConsumer method."""
    method = getattr(GearSyncConsumer, method_name)
    return inspect.getsource(method)


def _get_method_ast(method_name: str) -> ast.FunctionDef:
    """Get the AST for a GearSyncConsumer method."""
    source = _get_method_source(method_name)
    source = textwrap.dedent(source)
    tree = ast.parse(source)
    return tree.body[0]


# ---------------------------------------------------------------------------
# Bug 1: _poll_queue passes params as kwargs instead of dict
# ---------------------------------------------------------------------------


class TestPollQueueParamsBug:
    """_poll_queue must pass SQL params as a dict, not as kwargs.

    Current code (buggy):
        await self.t3k_session.execute(stmt, queue=queue_name, vt=60, qty=10)

    Fixed code:
        await self.t3k_session.execute(stmt, {"queue": queue_name, "vt": 60, "qty": 10})
    """

    def test_poll_queue_execute_uses_dict_params(self) -> None:
        """session.execute() must receive params as a mapping (dict), not kwargs.

        SQLAlchemy's execute() signature is execute(statement, parameters=None).
        Passing queue=, vt=, qty= as keyword arguments raises TypeError at runtime.
        """
        func_ast = _get_method_ast("_poll_queue")

        # Find the execute() call
        execute_calls = []
        for node in ast.walk(func_ast):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
            ):
                execute_calls.append(node)

        assert len(execute_calls) >= 1, "Expected at least one session.execute() call"

        call = execute_calls[0]

        # The execute call should have exactly 2 positional args:
        # execute(stmt, {"queue": ..., "vt": ..., "qty": ...})
        # NOT execute(stmt, queue=..., vt=..., qty=...)
        assert not any(kw.arg in ("queue", "vt", "qty") for kw in call.keywords), (
            "_poll_queue passes SQL params as kwargs (queue=, vt=, qty=) "
            "instead of a dict. This crashes at runtime with TypeError."
        )

        # Verify params are passed as a positional argument (dict) or via bindparams
        has_dict_param = len(call.args) >= 2
        has_bindparams = "bindparams" in _get_method_source("_poll_queue")
        assert has_dict_param or has_bindparams, (
            "_poll_queue must pass params as a dict positional arg or use .bindparams()"
        )


# ---------------------------------------------------------------------------
# Bug 1b: _poll_queue must rollback poisoned sessions on polling errors
# ---------------------------------------------------------------------------


class TestPollQueueSessionRecovery:
    """_poll_queue must rollback session state when polling raises."""

    async def test_poll_queue_rolls_back_on_poll_error(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Polling errors should trigger rollback so next poll can recover."""
        execute_tracker = AsyncTracker(side_effect=RuntimeError("simulated poll error"))
        rollback_tracker = AsyncTracker()
        monkeypatch.setattr(consumer.t3k_session, "execute", execute_tracker)
        monkeypatch.setattr(consumer.t3k_session, "rollback", rollback_tracker)

        messages = await consumer._poll_queue("gear_sync")

        assert messages == []
        assert rollback_tracker.call_count == 1


# ---------------------------------------------------------------------------
# Bug 2: _archive_message also passes params as kwargs
# ---------------------------------------------------------------------------


class TestArchiveMessageParamsBug:
    """_archive_message must pass SQL params as a dict, not as kwargs.

    Current code (buggy):
        await self.t3k_session.execute(stmt, queue=queue_name, msg_id=msg_id)

    Fixed code:
        await self.t3k_session.execute(stmt, {"queue": queue_name, "msg_id": msg_id})
    """

    def test_archive_message_execute_uses_dict_params(self) -> None:
        """session.execute() in _archive_message must receive params as dict."""
        func_ast = _get_method_ast("_archive_message")

        execute_calls = []
        for node in ast.walk(func_ast):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
            ):
                execute_calls.append(node)

        assert len(execute_calls) >= 1, "Expected at least one session.execute() call"

        call = execute_calls[0]

        # Must NOT have queue= or msg_id= as keyword args
        assert not any(kw.arg in ("queue", "msg_id") for kw in call.keywords), (
            "_archive_message passes SQL params as kwargs (queue=, msg_id=) "
            "instead of a dict. This crashes at runtime with TypeError."
        )

        # Must have dict param or bindparams
        has_dict_param = len(call.args) >= 2
        has_bindparams = "bindparams" in _get_method_source("_archive_message")
        assert has_dict_param or has_bindparams, (
            "_archive_message must pass params as a dict positional arg or use .bindparams()"
        )


# ---------------------------------------------------------------------------
# Bug 3: _dead_letter uses f-string SQL (SQL injection risk)
# ---------------------------------------------------------------------------


class TestDeadLetterSQLInjectionBug:
    """_dead_letter must use parameterised SQL, not f-string interpolation.

    Current code (buggy):
        stmt = text(f"SELECT pgmq.send('{self.dead_letter_queue}', CAST(:message AS jsonb))")

    This is vulnerable to SQL injection via the dead_letter_queue name.
    The queue name must be a bind parameter.
    """

    def test_dead_letter_does_not_use_fstring_sql(self) -> None:
        """_dead_letter must NOT use f-string for SQL construction."""
        source = _get_method_source("_dead_letter")

        # The f-string pattern that interpolates the queue name into SQL
        assert 'f"' not in source and "f'" not in source, (
            "_dead_letter uses f-string SQL which is vulnerable to SQL injection. "
            "The dead_letter_queue name must be a bind parameter."
        )

    def test_dead_letter_queue_name_is_parameterised(self) -> None:
        """The dead letter queue name must be passed as a SQL bind parameter."""
        source = _get_method_source("_dead_letter")

        # Should use :queue or :queue_name or similar bind param for the queue name
        # and NOT embed self.dead_letter_queue in the SQL string
        assert (
            "self.dead_letter_queue" not in source.split("text(")[1].split(")")[0]
            if "text(" in source
            else True
        ), (
            "_dead_letter embeds self.dead_letter_queue inside the text() SQL string. "
            "The queue name must be a bind parameter."
        )

    def test_dead_letter_execute_uses_dict_params(self) -> None:
        """session.execute() in _dead_letter must receive params as dict."""
        func_ast = _get_method_ast("_dead_letter")

        execute_calls = []
        for node in ast.walk(func_ast):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
            ):
                execute_calls.append(node)

        assert len(execute_calls) >= 1, "Expected at least one session.execute() call"

        call = execute_calls[0]

        # Must NOT have message= as keyword arg
        assert not any(kw.arg == "message" for kw in call.keywords), (
            "_dead_letter passes SQL params as kwargs (message=) "
            "instead of a dict. This crashes at runtime with TypeError."
        )


# ---------------------------------------------------------------------------
# Behaviour: dead-letter on read_ct > 5
# ---------------------------------------------------------------------------


class TestDeadLetterOnHighReadCount:
    """Consumer must dead-letter messages that have been read more than 5 times."""

    def test_poll_and_process_dead_letters_high_read_count(self) -> None:
        """_poll_and_process moves messages with read_ct > max_retries to dead letter queue."""
        source = inspect.getsource(GearSyncConsumer._poll_and_process)

        assert "read_ct" in source, "_poll_and_process must check message read_ct"
        assert "_dead_letter" in source, "_poll_and_process must call _dead_letter for retries"

    def test_dead_letter_threshold_is_5(self) -> None:
        """The read count threshold before dead-lettering is > 5."""
        source = inspect.getsource(GearSyncConsumer._poll_and_process)

        # The condition should check read_ct against retry threshold.
        assert "read_ct > self.max_retries" in source or "read_ct > 5" in source, (
            "Dead letter threshold must be read_ct > 5"
        )


# ---------------------------------------------------------------------------
# Behaviour: dead-letter on schema validation failure
# ---------------------------------------------------------------------------


class TestDeadLetterOnSchemaFailure:
    """Consumer must dead-letter messages that fail GearSyncRecord validation."""

    def test_poll_and_process_catches_processing_errors(self) -> None:
        """_poll_and_process catches processing exceptions and dead-letters messages."""
        source = inspect.getsource(GearSyncConsumer._poll_and_process)

        assert "except" in source, "_poll_and_process must catch processing exceptions"
        assert "_dead_letter" in source, "_poll_and_process must dead-letter failed messages"

    def test_dead_letter_archives_original_message(self) -> None:
        """_dead_letter must archive the original message from the source queue.

        After sending to dead letter queue, the original message should be
        archived (removed from the source queue) to prevent re-processing.
        """
        source = _get_method_source("_dead_letter")

        assert "_archive_message" in source, (
            "_dead_letter must archive the original message from the source queue"
        )


class TestRetryableErrorHandling:
    """Retryable failures should stay in main queue until retry budget is exhausted."""

    async def test_retryable_error_does_not_dead_letter(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        message = SimpleNamespace(
            read_ct=1,
            msg_id=101,
            message={
                "source_name": "t3k",
                "source_record_id": "pack-1",
                "source_updated_at": "2026-02-17T00:00:00+00:00",
                "operation": "create",
                "payload": {"name": "Pack 1", "slug": "pack-1", "gear_type": "amp"},
            },
        )

        poll_tracker = AsyncTracker(return_value=[message])
        dead_letter_tracker = AsyncTracker()
        archive_tracker = AsyncTracker()
        process_tracker = AsyncTracker(
            side_effect=RetryableGearSyncError("model file not ready"),
        )
        core_commit_tracker = AsyncTracker()
        core_rollback_tracker = AsyncTracker()
        t3k_commit_tracker = AsyncTracker()
        t3k_rollback_tracker = AsyncTracker()

        monkeypatch.setattr(consumer, "_poll_queue", poll_tracker)
        monkeypatch.setattr(consumer, "_dead_letter", dead_letter_tracker)
        monkeypatch.setattr(consumer, "_archive_message", archive_tracker)
        monkeypatch.setattr(consumer.mapper, "process_sync_record", process_tracker)
        monkeypatch.setattr(consumer.core_session, "commit", core_commit_tracker)
        monkeypatch.setattr(consumer.core_session, "rollback", core_rollback_tracker)
        monkeypatch.setattr(consumer.t3k_session, "commit", t3k_commit_tracker)
        monkeypatch.setattr(consumer.t3k_session, "rollback", t3k_rollback_tracker)

        await consumer._poll_and_process("gear_sync")

        assert not dead_letter_tracker.was_called
        assert not archive_tracker.was_called
        assert not core_commit_tracker.was_called
        assert not t3k_commit_tracker.was_called
        assert core_rollback_tracker.call_count == 1
        assert t3k_rollback_tracker.call_count == 1

    async def test_retryable_error_is_dead_lettered_after_max_retries(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        message = SimpleNamespace(
            read_ct=consumer.max_retries + 1,
            msg_id=102,
            message={"source_name": "t3k"},
        )

        poll_tracker = AsyncTracker(return_value=[message])
        dead_letter_tracker = AsyncTracker()
        process_tracker = AsyncTracker()
        t3k_commit_tracker = AsyncTracker()

        monkeypatch.setattr(consumer, "_poll_queue", poll_tracker)
        monkeypatch.setattr(consumer, "_dead_letter", dead_letter_tracker)
        monkeypatch.setattr(consumer.mapper, "process_sync_record", process_tracker)
        monkeypatch.setattr(consumer.t3k_session, "commit", t3k_commit_tracker)

        await consumer._poll_and_process("gear_sync")

        assert not process_tracker.was_called
        assert dead_letter_tracker.call_count == 1
        assert dead_letter_tracker.calls[0] == (message, "gear_sync")
        assert t3k_commit_tracker.call_count == 1


class TestStaleDlqCleanup:
    """Successful processing should cleanup stale DLQ entries for same source record."""

    async def test_successful_process_archives_stale_dlq_entries(
        self,
        consumer: GearSyncConsumer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        message = SimpleNamespace(
            read_ct=1,
            msg_id=103,
            message={
                "source_name": "t3k",
                "source_record_id": "pack-42",
                "source_updated_at": "2026-02-17T00:00:00+00:00",
                "operation": "create",
                "payload": {"name": "Pack 42", "slug": "pack-42", "gear_type": "amp"},
            },
        )

        poll_tracker = AsyncTracker(return_value=[message])
        process_tracker = AsyncTracker(return_value=None)
        cleanup_tracker = AsyncTracker()
        archive_tracker = AsyncTracker()
        core_commit_tracker = AsyncTracker()
        t3k_commit_tracker = AsyncTracker()

        monkeypatch.setattr(consumer, "_poll_queue", poll_tracker)
        monkeypatch.setattr(consumer.mapper, "process_sync_record", process_tracker)
        monkeypatch.setattr(consumer, "_archive_stale_dlq_for_record", cleanup_tracker)
        monkeypatch.setattr(consumer, "_archive_message", archive_tracker)
        monkeypatch.setattr(consumer.core_session, "commit", core_commit_tracker)
        monkeypatch.setattr(consumer.t3k_session, "commit", t3k_commit_tracker)

        await consumer._poll_and_process("gear_sync")

        assert process_tracker.call_count == 1
        assert cleanup_tracker.call_count == 1
        # Verify the record passed to cleanup has correct source info
        record = cleanup_tracker.calls[0][0]
        assert record.source_name == "t3k"
        assert record.source_record_id == "pack-42"
        assert archive_tracker.call_count == 1
        assert archive_tracker.calls[0] == ("gear_sync", 103)
        assert core_commit_tracker.call_count == 1
        assert t3k_commit_tracker.call_count == 1
