"""Root test fixtures providing PostgreSQL database sessions with SAVEPOINT isolation.

All tests use the real PostgreSQL database (DATABASE_URL from environment).
Per-test isolation is achieved via nested transactions (SAVEPOINTs):

    Session-scoped engine (created once, tables synced once)
      -> Function-scoped connection (BEGIN outer transaction)
        -> Function-scoped session (begin_nested SAVEPOINT)
          -> Test runs, service code calls commit() -> commits SAVEPOINT only
        -> After test: ROLLBACK outer transaction -> all changes gone

SQLite is BANNED. Never use sqlite+aiosqlite or in-memory SQLite for tests.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


class _SavepointSession(AsyncSession):
    """Session subclass that converts begin() to begin_nested() for SAVEPOINT isolation.

    Integration tests call ``async with session.begin():`` expecting to start a
    transaction.  Under the SAVEPOINT rollback pattern the session already has an
    active transaction, so a plain ``begin()`` would raise
    ``InvalidRequestError``.  This subclass transparently redirects to
    ``begin_nested()`` so that tests written for standalone transactions work
    unchanged inside the SAVEPOINT isolation harness.
    """

    def begin(self, **kw):  # type: ignore[override]
        return self.begin_nested()


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy import MetaData
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def _get_database_url() -> str:
    """Get DATABASE_URL from environment, required for all tests."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.fail("DATABASE_URL environment variable is required for tests")
    return url


def _sync_schema(connection: Connection, metadata: MetaData) -> None:
    """Sync ORM metadata with the database, adding missing tables and columns.

    create_all(checkfirst=True) only creates missing tables — it doesn't add
    columns to existing tables. This function handles both cases.
    """
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            table.create(connection, checkfirst=True)
        else:
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_columns:
                    col_type = column.type.compile(connection.engine.dialect)
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = ""
                    if column.server_default is not None:
                        default = f" DEFAULT {column.server_default.arg}"
                    connection.execute(
                        text(
                            f"ALTER TABLE {table.name} "
                            f"ADD COLUMN IF NOT EXISTS {column.name} {col_type} {nullable}{default}"
                        )
                    )


# ---------------------------------------------------------------------------
# Engine fixtures — session-scoped (one engine per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def core_engine(tmp_path_factory):
    """Session-scoped engine that ensures all tables (core + T3K) exist."""
    import asyncio

    from source_t3k.adapters.outbound.models import Base as T3KBase
    from webapp.adapters.persistence.models.base import Base as CoreBase

    engine = create_async_engine(_get_database_url(), echo=False, poolclass=NullPool)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(_sync_schema, CoreBase.metadata)
            await conn.run_sync(_sync_schema, T3KBase.metadata)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())
    yield engine
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture(scope="session")
def t3k_engine(core_engine):
    """Same engine as core_engine — T3K tables already synced in core_engine setup."""
    yield core_engine


# ---------------------------------------------------------------------------
# Function-scoped fixtures — per-test isolation via SAVEPOINT rollback
# ---------------------------------------------------------------------------


@pytest.fixture
async def core_connection(core_engine: AsyncEngine) -> AsyncGenerator[AsyncConnection, None]:
    """Function-scoped connection with outer transaction for rollback isolation."""
    async with core_engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()


@pytest.fixture
async def db_session(core_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped async session bound to a connection with SAVEPOINT isolation.

    When test code calls session.commit(), it commits only the SAVEPOINT.
    After the test, the outer transaction is rolled back, discarding all changes.
    """
    await core_connection.begin_nested()

    session = _SavepointSession(bind=core_connection, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _reopen_nested(_session, _transaction):
        if core_connection.closed:
            return
        if not core_connection.in_nested_transaction():
            core_connection.sync_connection.begin_nested()

    yield session

    await session.close()


@pytest.fixture
async def t3k_session(db_session: AsyncSession) -> AsyncSession:
    """Alias for db_session in single-database mode."""
    return db_session


@pytest.fixture
async def session(db_session: AsyncSession) -> AsyncSession:
    """Alias for db_session (backwards compatibility)."""
    return db_session
