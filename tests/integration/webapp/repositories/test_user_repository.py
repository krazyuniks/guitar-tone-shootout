"""Integration tests for UserRepository query patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.repositories.user_repository import SQLAlchemyUserRepository

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class QueryCounter:
    """Context manager to count SQL queries executed."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.count = 0

    def __enter__(self):
        """Start counting queries."""
        self.count = 0
        event.listen(self.engine.sync_engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop counting queries."""
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._before_cursor_execute)

    def _before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        """Callback fired before each query execution."""
        self.count += 1


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
def user_repository(db_session: AsyncSession) -> SQLAlchemyUserRepository:
    """Create a UserRepository instance."""
    return SQLAlchemyUserRepository(db_session)


@pytest.fixture
async def sample_user_with_identity(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> UserEntity:
    """Create and persist a user with identity."""
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
        avatar_url="https://example.com/avatar.jpg",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )

    await user_repository.save(user)
    await db_session.commit()

    return user


@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_get_by_identity_single_query(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
    db_engine: AsyncEngine,
    sample_user_with_identity: UserEntity,
) -> None:
    """Verify get_by_identity loads user and relationships in a single query.

    Citation: .claude/rules/query-patterns.md:100-111

    Tests that get_by_identity() uses chained joinedload for:
    - UserIdentity → User
    - UserIdentity → OAuthProvider

    Expected: 1 SQL query total (not 2 separate queries).
    Before refactor: 2 queries (SELECT provider, then SELECT user)
    After refactor: 1 query (SELECT user with JOINs)
    """
    # Expire all objects to force fresh query
    db_session.expire_all()

    # Count queries during get_by_identity
    with QueryCounter(db_engine) as counter:
        result = await user_repository.get_by_identity("t3k", "ext123")

    # Verify user loaded
    assert result is not None
    assert result.id == sample_user_with_identity.id

    # Verify all relationships loaded without additional queries
    assert result.username == "testuser"
    assert result.email == "test@example.com"
    assert len(result.identities) == 1
    assert result.identities[0].provider == "t3k"
    assert result.identities[0].external_id == "ext123"
    assert result.identities[0].username == "testuser"
    assert result.identities[0].avatar_url == "https://example.com/avatar.jpg"

    # Critical assertion: only ONE query executed (down from 2)
    assert counter.count == 1, f"Expected 1 query, got {counter.count}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_get_by_identity_uses_unique(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
    sample_user_with_identity: UserEntity,
) -> None:
    """Verify get_by_identity calls .unique() to deduplicate joined rows.

    Citation: .claude/rules/query-patterns.md:60

    When using joinedload with collections (1:N, M:N), JOINs produce
    duplicate parent rows that must be de-duplicated with .unique().
    """
    # Expire all objects
    db_session.expire_all()

    # Execute get_by_identity
    result = await user_repository.get_by_identity("t3k", "ext123")

    # Verify no duplicates: should return single entity, not multiple
    assert result is not None
    assert isinstance(result, UserEntity)

    # Verify identity collection is properly loaded (not duplicated)
    assert len(result.identities) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_get_by_identity_same_behavior_as_before(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Verify get_by_identity returns same results as before refactor.

    Tests edge cases:
    - Provider not found → returns None
    - External ID not found → returns None
    - Multiple users with different providers → returns correct user
    """
    # Create user with identity
    identity = UserIdentity(
        provider="t3k",
        external_id="ext456",
        username="user1",
    )
    user1 = UserEntity.create_with_identity(
        identity=identity,
        email="user1@example.com",
    )
    await user_repository.save(user1)

    # Create second user with different provider
    identity2 = UserIdentity(
        provider="google",
        external_id="google789",
        username="user2",
    )
    user2 = UserEntity.create_with_identity(
        identity=identity2,
        email="user2@example.com",
    )
    await user_repository.save(user2)

    await db_session.commit()

    # Test: Found user
    result = await user_repository.get_by_identity("t3k", "ext456")
    assert result is not None
    assert result.id == user1.id
    assert result.email == "user1@example.com"

    # Test: Different provider
    result = await user_repository.get_by_identity("google", "google789")
    assert result is not None
    assert result.id == user2.id
    assert result.email == "user2@example.com"

    # Test: Provider not found
    result = await user_repository.get_by_identity("unknown_provider", "ext456")
    assert result is None

    # Test: External ID not found
    result = await user_repository.get_by_identity("t3k", "nonexistent")
    assert result is None
