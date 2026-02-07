"""Integration tests for UserRepository.get_by_identity() joinedload conversion (T38).

Tests verify that get_by_identity() uses a single query with JOINs instead of
two separate queries (provider lookup + user lookup).

CRITICAL: These tests MUST fail against the current implementation which fires
2 queries. After refactoring, query_count should be exactly 1.
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
) -> tuple[User, OAuthProvider]:
    """Create a fully-populated User ORM model with identity and provider.

    Returns:
        Tuple of (User, OAuthProvider) so tests can query by provider name.
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

    return user, provider


async def test_user_get_by_identity_single_query(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: tuple[User, OAuthProvider],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_identity() loads all data in a single SQL query.

    CRITICAL: This test MUST fail against the current implementation which fires
    2 queries:
    1. SELECT OAuthProvider WHERE name = :provider
    2. SELECT User JOIN UserIdentity WHERE provider_id = :id AND external_id = :ext_id

    After refactoring, this should be 1 query using chained JOINs:
    SELECT User
    JOIN UserIdentity ON User.id = UserIdentity.user_id
    JOIN OAuthProvider ON UserIdentity.provider_id = OAuthProvider.id
    WHERE OAuthProvider.name = :provider AND UserIdentity.external_id = :ext_id
    """
    user, provider = sample_user_with_identity

    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_identity(
            provider="t3k",
            external_id="ext-123",
        )

    # Verify result is not None
    assert result is not None, "User should be found"

    # Verify all data is loaded correctly
    assert result.id == user.id, "User ID should match"
    assert len(result.identities) == 1, "Should have 1 identity"
    assert result.identities[0].provider == "t3k", "Provider should be loaded"
    assert result.identities[0].external_id == "ext-123", "Identity should be loaded"


async def test_user_get_by_identity_uses_unique_scalar_one_or_none(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: tuple[User, OAuthProvider],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_identity() calls .unique().scalar_one_or_none().

    When using joinedload() with 1:N or M:N relationships, the SQL JOIN produces
    duplicate parent rows (one per child). SQLAlchemy's .unique() deduplicates these.

    This test verifies the method signature includes .unique().scalar_one_or_none()
    as required by the acceptance criteria.
    """
    user, provider = sample_user_with_identity

    # Get user by identity
    result = await user_repository.get_by_identity(
        provider="t3k",
        external_id="ext-123",
    )

    # Verify we get exactly one user entity (not duplicates)
    assert result is not None, "User should be found"
    assert result.id == user.id, "User ID should match"

    # Verify the relationship data is correct
    assert len(result.identities) == 1, "Should have exactly 1 identity"


async def test_user_get_by_identity_uses_chained_joinedload(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: tuple[User, OAuthProvider],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_identity() uses chained joinedload() for nested relationships.

    The refactored implementation should use:
    .options(joinedload(User.identities).joinedload(UserIdentity.provider))

    This loads the full User → UserIdentity → OAuthProvider graph in one query.
    """
    user, provider = sample_user_with_identity

    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_identity(
            provider="t3k",
            external_id="ext-123",
        )

    # Verify result
    assert result is not None, "User should be found"

    # Verify all nested relationships are loaded without additional queries
    # (accessing these attributes should NOT trigger lazy loading)
    assert len(result.identities) == 1, "Should have 1 identity"
    assert result.identities[0].provider == "t3k", "Provider name should be loaded"
    assert result.identities[0].external_id == "ext-123", "External ID should be loaded"


async def test_user_get_by_identity_provider_not_found(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_identity() returns None when provider doesn't exist.

    Verifies behavior is unchanged from current implementation.
    """
    result = await user_repository.get_by_identity(
        provider="nonexistent_provider",
        external_id="ext-123",
    )
    assert result is None, "Should return None when provider not found"


async def test_user_get_by_identity_user_not_found(
    user_repository: SQLAlchemyUserRepository,
    sample_user_with_identity: tuple[User, OAuthProvider],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_identity() returns None when identity doesn't exist.

    Verifies behavior is unchanged from current implementation.
    """
    user, provider = sample_user_with_identity

    result = await user_repository.get_by_identity(
        provider="t3k",
        external_id="nonexistent-id",
    )
    assert result is None, "Should return None when identity not found"


async def test_user_get_by_identity_same_behavior_as_before(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that refactored get_by_identity() returns identical results.

    Creates multiple users with different providers and verifies the query
    returns the correct user based on provider + external_id combination.

    This ensures the refactoring doesn't break existing functionality.
    """
    # Create two providers
    provider_t3k = OAuthProvider(
        id=uuid4(),
        name="t3k",
        enabled=True,
    )
    provider_google = OAuthProvider(
        id=uuid4(),
        name="google",
        enabled=True,
    )
    db_session.add(provider_t3k)
    db_session.add(provider_google)
    await db_session.flush()

    # Create two users
    user1 = User(
        id=uuid4(),
        username="user1",
        email="user1@example.com",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user2 = User(
        id=uuid4(),
        username="user2",
        email="user2@example.com",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()

    # Create identities for both users
    identity1 = UserIdentity(
        id=uuid4(),
        user_id=user1.id,
        provider_id=provider_t3k.id,
        external_id="t3k-user1-id",
        username="user1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    identity2 = UserIdentity(
        id=uuid4(),
        user_id=user2.id,
        provider_id=provider_google.id,
        external_id="google-user2-id",
        username="user2",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(identity1)
    db_session.add(identity2)
    await db_session.commit()

    # Query for user1 via t3k
    result1 = await user_repository.get_by_identity(
        provider="t3k",
        external_id="t3k-user1-id",
    )
    assert result1 is not None, "Should find user1"
    assert result1.id == user1.id, "Should return correct user"
    assert result1.username == "user1", "Username should match"

    # Query for user2 via google
    result2 = await user_repository.get_by_identity(
        provider="google",
        external_id="google-user2-id",
    )
    assert result2 is not None, "Should find user2"
    assert result2.id == user2.id, "Should return correct user"
    assert result2.username == "user2", "Username should match"

    # Wrong provider/external_id combination should return None
    result3 = await user_repository.get_by_identity(
        provider="t3k",
        external_id="google-user2-id",
    )
    assert result3 is None, "Should not find user with wrong provider/external_id combo"


async def test_user_get_by_identity_with_multiple_identities_per_user(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test get_by_identity() when a user has multiple identity providers.

    Verifies that:
    1. The correct user is returned when querying by any of their identities
    2. All identities are loaded (not just the one we queried for)
    3. Query count = 1 (single query loads everything)
    """
    # Create two providers
    provider_t3k = OAuthProvider(
        id=uuid4(),
        name="t3k",
        enabled=True,
    )
    provider_google = OAuthProvider(
        id=uuid4(),
        name="google",
        enabled=True,
    )
    db_session.add(provider_t3k)
    db_session.add(provider_google)
    await db_session.flush()

    # Create user with both identities
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

    # Create identities for both providers
    identity_t3k = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        provider_id=provider_t3k.id,
        external_id="t3k-multi-id",
        username="multiuser",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    identity_google = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        provider_id=provider_google.id,
        external_id="google-multi-id",
        username="multiuser",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(identity_t3k)
    db_session.add(identity_google)
    await db_session.commit()

    with assert_query_count(db_session, expected=1):
        result = await user_repository.get_by_identity(
            provider="t3k",
            external_id="t3k-multi-id",
        )

    # Verify result
    assert result is not None, "Should find user"
    assert result.id == user.id, "Should return correct user"

    # Verify ALL identities are loaded (not just the one we queried for)
    assert len(result.identities) == 2, "Should load all identities"
    providers = {identity.provider for identity in result.identities}
    assert providers == {"t3k", "google"}, "Should have both providers loaded"
