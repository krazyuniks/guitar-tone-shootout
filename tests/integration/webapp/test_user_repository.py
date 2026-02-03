"""Integration tests for UserRepository."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider
from webapp.adapters.persistence.repositories.user_repository import (
    SQLAlchemyUserRepository,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Clean up
    await engine.dispose()


@pytest.fixture
async def user_repository(db_session: AsyncSession) -> SQLAlchemyUserRepository:
    """Create a UserRepository instance."""
    return SQLAlchemyUserRepository(db_session)


@pytest.mark.asyncio
async def test_save_and_get_by_id(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test saving a user and retrieving by ID."""
    # Create user with identity
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

    # Save user
    await user_repository.save(user)
    await db_session.commit()

    # Retrieve user
    retrieved = await user_repository.get_by_id(user.id)

    # Verify
    assert retrieved is not None
    assert retrieved.id == user.id
    assert retrieved.username == user.username
    assert retrieved.email == user.email
    assert retrieved.avatar_url == user.avatar_url
    assert len(retrieved.identities) == 1
    assert retrieved.identities[0].provider == "t3k"
    assert retrieved.identities[0].external_id == "ext123"
    assert retrieved.identities[0].username == "testuser"


@pytest.mark.asyncio
async def test_get_by_id_not_found(
    user_repository: SQLAlchemyUserRepository,
) -> None:
    """Test getting a user that doesn't exist."""
    result = await user_repository.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_by_email(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test retrieving a user by email."""
    # Create user
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )

    # Save user
    await user_repository.save(user)
    await db_session.commit()

    # Retrieve by email
    retrieved = await user_repository.get_by_email("test@example.com")

    # Verify
    assert retrieved is not None
    assert retrieved.id == user.id
    assert retrieved.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_by_email_not_found(
    user_repository: SQLAlchemyUserRepository,
) -> None:
    """Test getting a user by email that doesn't exist."""
    result = await user_repository.get_by_email("nonexistent@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_identity(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test retrieving a user by external identity."""
    # Create user
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )

    # Save user
    await user_repository.save(user)
    await db_session.commit()

    # Retrieve by identity
    retrieved = await user_repository.get_by_identity("t3k", "ext123")

    # Verify
    assert retrieved is not None
    assert retrieved.id == user.id
    assert len(retrieved.identities) == 1
    assert retrieved.identities[0].provider == "t3k"
    assert retrieved.identities[0].external_id == "ext123"


@pytest.mark.asyncio
async def test_get_by_identity_not_found(
    user_repository: SQLAlchemyUserRepository,
) -> None:
    """Test getting a user by identity that doesn't exist."""
    result = await user_repository.get_by_identity("t3k", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_identity_provider_not_found(
    user_repository: SQLAlchemyUserRepository,
) -> None:
    """Test getting a user with unknown provider."""
    result = await user_repository.get_by_identity("unknown_provider", "ext123")
    assert result is None


@pytest.mark.asyncio
async def test_update_user(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test updating an existing user."""
    # Create and save initial user
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )
    await user_repository.save(user)
    await db_session.commit()

    # Update user
    user.update_username("newusername")
    await user_repository.save(user)
    await db_session.commit()

    # Retrieve and verify
    retrieved = await user_repository.get_by_id(user.id)
    assert retrieved is not None
    assert retrieved.username == "newusername"


@pytest.mark.asyncio
async def test_delete_user(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test deleting a user."""
    # Create and save user
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )
    await user_repository.save(user)
    await db_session.commit()

    # Delete user
    await user_repository.delete(user.id)
    await db_session.commit()

    # Verify deletion
    retrieved = await user_repository.get_by_id(user.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_nonexistent_user(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test deleting a user that doesn't exist (should not raise)."""
    # Should not raise an error
    await user_repository.delete(uuid.uuid4())
    await db_session.commit()


@pytest.mark.asyncio
async def test_save_user_with_multiple_identities(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test saving a user with multiple identities."""
    # Create user with first identity
    identity1 = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity1,
        email="test@example.com",
    )

    # Add second identity
    identity2 = UserIdentity(
        provider="google",
        external_id="google123",
        username="testuser@gmail.com",
    )
    user.add_identity(identity2)

    # Save user
    await user_repository.save(user)
    await db_session.commit()

    # Retrieve and verify
    retrieved = await user_repository.get_by_id(user.id)
    assert retrieved is not None
    assert len(retrieved.identities) == 2

    providers = {ident.provider for ident in retrieved.identities}
    assert "t3k" in providers
    assert "google" in providers


@pytest.mark.asyncio
async def test_update_user_identities(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test updating user identities."""
    # Create user with identity
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )
    await user_repository.save(user)
    await db_session.commit()

    # Remove identity and add new one
    user.remove_identity("t3k")
    new_identity = UserIdentity(
        provider="google",
        external_id="google123",
        username="testuser@gmail.com",
    )
    user.add_identity(new_identity)

    await user_repository.save(user)
    await db_session.commit()

    # Retrieve and verify
    retrieved = await user_repository.get_by_id(user.id)
    assert retrieved is not None
    assert len(retrieved.identities) == 1
    assert retrieved.identities[0].provider == "google"


@pytest.mark.asyncio
async def test_provider_created_if_missing(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> None:
    """Test that OAuth provider is created if it doesn't exist."""
    # Create user with identity for new provider
    identity = UserIdentity(
        provider="new_provider",
        external_id="ext123",
        username="testuser",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )

    # Save user (should create provider)
    await user_repository.save(user)
    await db_session.commit()

    # Verify provider was created
    from sqlalchemy import select

    stmt = select(OAuthProvider).where(OAuthProvider.name == "new_provider")
    result = await db_session.execute(stmt)
    provider = result.scalar_one_or_none()

    assert provider is not None
    assert provider.name == "new_provider"
    assert provider.enabled is True
