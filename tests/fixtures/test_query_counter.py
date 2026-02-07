"""Unit tests for query counting fixture.

Tests for T42: Add query counting fixture for integration tests
Verifies that the query counter correctly counts SQL queries executed during a test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.fixtures.query_counter import assert_query_count
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session()

    try:
        yield session
    finally:
        if session.in_transaction():
            await session.rollback()
        await session.close()


class TestQueryCounter:
    """Tests for query counting fixture."""

    async def test_counts_single_query(self, db_session: AsyncSession) -> None:
        """Verify fixture counts a single SELECT query."""
        with assert_query_count(db_session, expected=1):
            await db_session.execute(select(User))

    async def test_counts_multiple_queries(self, db_session: AsyncSession) -> None:
        """Verify fixture counts multiple queries."""
        with assert_query_count(db_session, expected=3):
            await db_session.execute(select(User))
            await db_session.execute(text("SELECT 1"))
            await db_session.execute(select(User).limit(1))

    async def test_counts_zero_queries(self, db_session: AsyncSession) -> None:
        """Verify fixture works when no queries are executed."""
        with assert_query_count(db_session, expected=0):
            # No database operations
            pass

    async def test_fails_when_count_mismatch(self, db_session: AsyncSession) -> None:
        """Verify fixture raises AssertionError when query count doesn't match."""
        with pytest.raises(AssertionError, match="Expected 1 queries, but 2 were executed"):
            with assert_query_count(db_session, expected=1):
                await db_session.execute(select(User))
                await db_session.execute(select(User))

    async def test_counts_insert_queries(self, db_session: AsyncSession) -> None:
        """Verify fixture counts INSERT queries."""
        from uuid import uuid4

        with assert_query_count(db_session, expected=1):
            user = User(
                id=uuid4(),
                username="testuser",
                email="test@example.com",
            )
            db_session.add(user)
            await db_session.flush()

    async def test_counts_update_queries(self, db_session: AsyncSession) -> None:
        """Verify fixture counts UPDATE queries."""
        from uuid import uuid4

        # Setup: create a user (not counted)
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.expire_all()

        # Test: update should count as 2 queries (SELECT + UPDATE)
        with assert_query_count(db_session, expected=2):
            result = await db_session.execute(
                select(User).where(User.id == user.id)
            )
            loaded_user = result.scalar_one()
            loaded_user.username = "newname"
            await db_session.flush()

    async def test_counts_delete_queries(self, db_session: AsyncSession) -> None:
        """Verify fixture counts DELETE queries."""
        from uuid import uuid4

        # Setup: create a user (not counted)
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.expire_all()

        # Test: delete should count as 2 queries (SELECT + DELETE)
        with assert_query_count(db_session, expected=2):
            result = await db_session.execute(
                select(User).where(User.id == user.id)
            )
            loaded_user = result.scalar_one()
            await db_session.delete(loaded_user)
            await db_session.flush()

    async def test_works_with_transaction_context(self, db_session: AsyncSession) -> None:
        """Verify fixture works within transaction blocks."""
        from uuid import uuid4

        async with db_session.begin():
            with assert_query_count(db_session, expected=1):
                user = User(
                    id=uuid4(),
                    username="testuser",
                    email="test@example.com",
                )
                db_session.add(user)
                await db_session.flush()

    async def test_resets_count_between_uses(self, db_session: AsyncSession) -> None:
        """Verify counter resets between context manager uses."""
        # First use
        with assert_query_count(db_session, expected=1):
            await db_session.execute(select(User))

        # Second use - should start from 0 again
        with assert_query_count(db_session, expected=1):
            await db_session.execute(select(User))

    async def test_counts_queries_with_joinedload(self, db_session: AsyncSession) -> None:
        """Verify fixture counts queries with eager loading."""
        from sqlalchemy.orm import joinedload

        # This should be a single query with JOINs
        with assert_query_count(db_session, expected=1):
            await db_session.execute(
                select(User).options(
                    joinedload(User.identities)
                )
            )
