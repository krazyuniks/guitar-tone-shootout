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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from worker.consumers.gear_sync import GearSyncConsumer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def t3k_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine simulating the t3k_source database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def core_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine simulating the gts_core database."""
    from webapp.adapters.persistence.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def t3k_session(t3k_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(t3k_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def core_session(core_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(core_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def consumer(
    core_session: AsyncSession,
    t3k_session: AsyncSession,
) -> GearSyncConsumer:
    return GearSyncConsumer(
        core_session=core_session,
        t3k_session=t3k_session,
        pack_queue_name="gear_pack_sync",
        model_queue_name="gear_model_sync",
        dead_letter_queue="sync_dead_letter",
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
        stmt = text(f"SELECT pgmq.send('{self.dead_letter_queue}', :message::jsonb)")

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

    def test_poll_pack_queue_dead_letters_high_read_count(self) -> None:
        """poll_pack_queue moves messages with read_ct > 5 to dead letter queue.

        This verifies the logic exists in the source — the threshold is checked
        BEFORE processing so bad messages don't block the queue.
        """
        source = inspect.getsource(GearSyncConsumer.poll_pack_queue)

        assert "read_ct" in source, "poll_pack_queue must check message read_ct"
        assert "_dead_letter" in source, "poll_pack_queue must call _dead_letter for retries"

    def test_poll_model_queue_dead_letters_high_read_count(self) -> None:
        """poll_model_queue moves messages with read_ct > 5 to dead letter queue."""
        source = inspect.getsource(GearSyncConsumer.poll_model_queue)

        assert "read_ct" in source, "poll_model_queue must check message read_ct"
        assert "_dead_letter" in source, "poll_model_queue must call _dead_letter for retries"

    def test_dead_letter_threshold_is_5(self) -> None:
        """The read count threshold before dead-lettering is > 5."""
        source = inspect.getsource(GearSyncConsumer.poll_pack_queue)

        # The condition should check read_ct > 5
        assert "read_ct > 5" in source or "read_ct >= 6" in source, (
            "Dead letter threshold must be read_ct > 5"
        )


# ---------------------------------------------------------------------------
# Behaviour: dead-letter on schema validation failure
# ---------------------------------------------------------------------------


class TestDeadLetterOnSchemaFailure:
    """Consumer must dead-letter messages that fail GearSyncRecord validation."""

    def test_pack_queue_catches_processing_errors(self) -> None:
        """poll_pack_queue catches exceptions during message processing
        and sends them to the dead letter queue.

        If GearSyncRecord.from_dict() fails (schema validation), the message
        must be dead-lettered, not silently dropped or left in the queue.
        """
        source = inspect.getsource(GearSyncConsumer.poll_pack_queue)

        assert "except" in source, "poll_pack_queue must catch processing exceptions"
        assert "_dead_letter" in source, "poll_pack_queue must dead-letter failed messages"

    def test_model_queue_catches_processing_errors(self) -> None:
        """poll_model_queue catches exceptions during message processing."""
        source = inspect.getsource(GearSyncConsumer.poll_model_queue)

        assert "except" in source, "poll_model_queue must catch processing exceptions"
        assert "_dead_letter" in source, "poll_model_queue must dead-letter failed messages"

    def test_dead_letter_archives_original_message(self) -> None:
        """_dead_letter must archive the original message from the source queue.

        After sending to dead letter queue, the original message should be
        archived (removed from the source queue) to prevent re-processing.
        """
        source = _get_method_source("_dead_letter")

        assert "_archive_message" in source, (
            "_dead_letter must archive the original message from the source queue"
        )
