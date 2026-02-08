"""Integration tests for UserRepository joinedload conversion (T37).

Tests verify that get_by_id() and get_by_email() use joinedload() for single-query
eager loading of all relationships (identities, provider).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.fixtures.query_counter import assert_query_count
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.user import User as UserEntity
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity
from webapp.adapters.persistence.repositories.user_repository import SQLAlchemyUserRepository

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with query tracking.

    Uses in-memory SQLite for fast, isolated testing.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Yield session
    async with session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def user_repository(db_session: AsyncSession) -> SQLAlchemyUserRepository:
    """Create a UserRepository instance."""
    return SQLAlchemyUserRepository(db_session)


@pytest.fixture
async def sample_user_with_identity(
    db_session: AsyncSession,
) -> User:
    """Create a fully-populated User ORM model with identity and provider.

    Returns the ORM model (not entity) so tests can verify relationship loading.
    """
    # Create an OAuth provider
    provider = OAuthProvider(
        id=uuid4(),
        name="t3k",
        client_id="test-client-id",
        client_secret="test-client-secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.flush()

    # Create user
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        avatar_url="https://example.com/avatar.jpg",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()

    # Create user identity
    identity = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        provider_id=provider.id,
        external_id="ext-123",
        username="testuser",
        avatar_url="https://example.com/avatar.jpg",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(identity)
    await db_session.commit()

    return user


async def test_user_get_by_id_single_query(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses chained joinedload(User.identities).joinedload(UserIdentity.provider)
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 3 queries (1 + 2 relationships).
    """
    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_id(sample_user_with_identity.id)

    # Verify result is not None
    assert result is not None, "User should be found"

    # Verify all relationships are loaded (no lazy loading should occur)
    assert len(result.identities) == 1, "Should have 1 identity"
    assert result.identities[0].provider == "t3k", "Provider should be loaded"
    assert result.identities[0].external_id == "ext-123", "Identity should be loaded"


async def test_user_get_by_id_uses_unique_scalar_one_or_none(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() calls .unique() to deduplicate JOIN rows.

    When using joinedload() with 1:N or M:N relationships, the SQL JOIN produces
    duplicate parent rows (one per child). SQLAlchemy's .unique() deduplicates these.

    This test verifies that .unique() is called, which is required for correct results.
    Without .unique(), queries with multiple children return duplicate parent entities.
    """
    # Get user
    result = await user_repository.get_by_id(sample_user_with_identity.id)

    # Verify we get exactly one user entity (not duplicates)
    assert result is not None, "User should be found"
    assert result.id == sample_user_with_identity.id, "User ID should match"

    # Verify the relationship data is correct
    assert len(result.identities) == 1, "Should have exactly 1 identity"


async def test_user_get_by_email_single_query(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_email() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses chained joinedload(User.identities).joinedload(UserIdentity.provider)
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 3 queries (1 + 2 relationships).
    """
    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_email(sample_user_with_identity.email)

    # Verify result is not None
    assert result is not None, "User should be found"

    # Verify all relationships are loaded (no lazy loading should occur)
    assert len(result.identities) == 1, "Should have 1 identity"
    assert result.identities[0].provider == "t3k", "Provider should be loaded"
    assert result.identities[0].external_id == "ext-123", "Identity should be loaded"


async def test_user_get_by_email_uses_unique_scalar_one_or_none(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_email() calls .unique() to deduplicate JOIN rows.

    When using joinedload() with 1:N or M:N relationships, the SQL JOIN produces
    duplicate parent rows (one per child). SQLAlchemy's .unique() deduplicates these.

    This test verifies that .unique() is called, which is required for correct results.
    Without .unique(), queries with multiple children return duplicate parent entities.
    """
    # Get user
    result = await user_repository.get_by_email(sample_user_with_identity.email)

    # Verify we get exactly one user entity (not duplicates)
    assert result is not None, "User should be found"
    assert result.email == sample_user_with_identity.email, "User email should match"

    # Verify the relationship data is correct
    assert len(result.identities) == 1, "Should have exactly 1 identity"


async def test_user_get_by_id_with_multiple_identities(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() correctly loads users with multiple identities.

    Verifies that .unique() properly deduplicates JOIN rows when a user has
    multiple identities (one per provider).
    """
    # Create multiple providers
    provider1 = OAuthProvider(
        id=uuid4(),
        name="t3k",
        enabled=True,
    )
    provider2 = OAuthProvider(
        id=uuid4(),
        name="google",
        enabled=True,
    )
    db_session.add(provider1)
    db_session.add(provider2)
    await db_session.flush()

    # Create user
    user = User(
        id=uuid4(),
        username="multiuser",
        email="multi@example.com",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()

    # Create multiple identities
    identity1 = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        provider_id=provider1.id,
        external_id="ext-t3k-123",
        username="multiuser",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    identity2 = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        provider_id=provider2.id,
        external_id="ext-google-456",
        username="multiuser",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(identity1)
    db_session.add(identity2)
    await db_session.commit()

    # Execute get_by_id with query counting
    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_id(user.id)

    # Verify result
    assert result is not None, "User should be found"

    # Verify both identities are loaded correctly
    assert len(result.identities) == 2, "Should have 2 identities"
    providers = {identity.provider for identity in result.identities}
    assert providers == {"t3k", "google"}, "Should have both providers"


async def test_user_get_by_id_not_found(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() returns None when user is not found."""
    nonexistent_id = uuid4()
    result = await user_repository.get_by_id(nonexistent_id)
    assert result is None, "Should return None for nonexistent user"


async def test_user_get_by_email_not_found(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_email() returns None when user is not found."""
    result = await user_repository.get_by_email("nonexistent@example.com")
    assert result is None, "Should return None for nonexistent email"
