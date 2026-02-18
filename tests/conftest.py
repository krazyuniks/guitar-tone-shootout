"""Root test fixtures providing PostgreSQL database sessions with SAVEPOINT isolation.

All tests use the real PostgreSQL database (DATABASE_URL from environment).
Per-test isolation is achieved via nested transactions (SAVEPOINTs):

    Function-scoped connection (BEGIN outer transaction)
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
# Engine fixtures — create engine + tables per test function
# ---------------------------------------------------------------------------


@pytest.fixture
async def core_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine that ensures core (webapp) tables exist and schema is synced."""
    from webapp.adapters.persistence.models.base import Base as CoreBase

    engine = create_async_engine(_get_database_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_sync_schema, CoreBase.metadata)
    yield engine
    await engine.dispose()


@pytest.fixture
async def t3k_engine(core_engine: AsyncEngine) -> AsyncGenerator[AsyncEngine, None]:
    """Engine that also ensures T3K staging tables exist.

    Reuses the core_engine (same database), just creates T3K tables too.
    """
    from source_t3k.adapters.outbound.models import Base as T3KBase

    async with core_engine.begin() as conn:
        await conn.run_sync(_sync_schema, T3KBase.metadata)
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

    session = AsyncSession(bind=core_connection, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _reopen_nested(_session, _transaction):
        if core_connection.closed:
            return
        if not core_connection.in_nested_transaction():
            core_connection.sync_connection.begin_nested()

    yield session

    await session.close()


@pytest.fixture
async def t3k_session(t3k_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped session for T3K staging table tests.

    Same SAVEPOINT isolation pattern as db_session, but depends on t3k_engine
    to ensure T3K tables exist.
    """
    async with t3k_engine.connect() as conn:
        trans = await conn.begin()
        await conn.begin_nested()

        session = AsyncSession(bind=conn, expire_on_commit=False)

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _reopen_nested(_session, _transaction):
            if conn.closed:
                return
            if not conn.in_nested_transaction():
                conn.sync_connection.begin_nested()

        yield session

        await session.close()
        await trans.rollback()


@pytest.fixture
async def session(db_session: AsyncSession) -> AsyncSession:
    """Alias for db_session (backwards compatibility)."""
    return db_session
