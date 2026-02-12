"""Unit tests for User ORM models."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
    # Use async SQLite for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_model_creates_with_correct_fields(db_session: AsyncSession) -> None:
    """Test User model creates with all required fields."""
    user = User(
        username="test_user",
        email="test@example.com",
        avatar_url="https://example.com/avatar.png",
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify fields
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.username == "test_user"
    assert user.email == "test@example.com"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


@pytest.mark.asyncio
async def test_user_identity_links_to_user(db_session: AsyncSession) -> None:
    """Test UserIdentity properly links to User."""
    # Create OAuth provider first
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    # Create user
    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create identity linking to user and provider
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="12345",
        username="external_user",
        avatar_url="https://provider.com/avatar.png",
    )
    db_session.add(identity)
    await db_session.commit()

    # Store ID for fresh query
    user_id = user.id

    # Close session and create new one for fresh query
    await db_session.close()

    # Create new session
    async_session = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    new_session = async_session()

    # Query back and verify relationships
    result = await new_session.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    loaded_user = result.unique().scalar_one()

    assert len(loaded_user.identities) == 1
    assert loaded_user.identities[0].external_id == "12345"
    assert loaded_user.identities[0].username == "external_user"
    assert loaded_user.identities[0].provider.name == "t3k"


@pytest.mark.asyncio
async def test_user_has_many_identities(db_session: AsyncSession) -> None:
    """Test User can have multiple UserIdentities."""
    # Create providers
    t3k = OAuthProvider(name="t3k", enabled=True)
    google = OAuthProvider(name="google", enabled=True)
    db_session.add_all([t3k, google])
    await db_session.commit()

    # Create user
    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add multiple identities
    identity1 = UserIdentity(
        user_id=user.id,
        provider_id=t3k.id,
        external_id="t3k_123",
        username="t3k_user",
    )
    identity2 = UserIdentity(
        user_id=user.id,
        provider_id=google.id,
        external_id="google_456",
        username="google_user",
    )
    db_session.add_all([identity1, identity2])
    await db_session.commit()

    # Store ID for fresh query
    user_id = user.id

    # Close session and create new one for fresh query
    await db_session.close()

    # Create new session
    async_session = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    new_session = async_session()

    # Query and verify
    result = await new_session.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    loaded_user = result.unique().scalar_one()

    assert len(loaded_user.identities) == 2
    provider_names = {identity.provider.name for identity in loaded_user.identities}
    assert provider_names == {"t3k", "google"}


@pytest.mark.asyncio
async def test_email_index_exists(db_session: AsyncSession) -> None:
    """Test email column has an index for performance."""
    # Create two users with different emails
    user1 = User(username="user1", email="user1@example.com")
    user2 = User(username="user2", email="user2@example.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # Query by email (should use index)
    result = await db_session.execute(select(User).where(User.email == "user1@example.com"))
    found = result.scalar_one()

    assert found.username == "user1"


@pytest.mark.asyncio
async def test_provider_lookup_index(db_session: AsyncSession) -> None:
    """Test provider lookups have proper indexes."""
    # Create provider and users
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    user1 = User(username="user1")
    user2 = User(username="user2")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # Create identities
    identity1 = UserIdentity(
        user_id=user1.id,
        provider_id=provider.id,
        external_id="123",
        username="user1_external",
    )
    identity2 = UserIdentity(
        user_id=user2.id,
        provider_id=provider.id,
        external_id="456",
        username="user2_external",
    )
    db_session.add_all([identity1, identity2])
    await db_session.commit()

    # Query by provider and external_id (should use composite index)
    result = await db_session.execute(
        select(UserIdentity).where(
            UserIdentity.provider_id == provider.id,
            UserIdentity.external_id == "123",
        )
    )
    found = result.scalar_one()

    assert found.username == "user1_external"


@pytest.mark.asyncio
async def test_oauth_provider_model(db_session: AsyncSession) -> None:
    """Test OAuthProvider model."""
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.id is not None
    assert provider.name == "t3k"
    assert provider.enabled is True
