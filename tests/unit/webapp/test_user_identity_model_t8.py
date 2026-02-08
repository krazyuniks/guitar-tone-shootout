"""Unit tests for UserIdentity ORM model extraction (T8).

This task extracts UserIdentity into its own module file.
Tests verify the model can be imported from user_identity.py.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User

# This import MUST work after T8 implementation
from webapp.adapters.persistence.models.user_identity import UserIdentity


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
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
async def test_user_identity_importable_from_user_identity_module(
    db_session: AsyncSession,
) -> None:
    """Test UserIdentity can be imported from user_identity.py module."""
    # If this test runs, the import at the top succeeded
    # Now verify the model works with the database
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create identity using the imported UserIdentity
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="external_123",
        username="external_user",
    )
    db_session.add(identity)
    await db_session.commit()
    await db_session.refresh(identity)

    # Verify it persisted correctly
    assert identity.id is not None
    assert isinstance(identity.id, uuid.UUID)
    assert identity.user_id == user.id
    assert identity.provider_id == provider.id


@pytest.mark.asyncio
async def test_user_identity_has_all_required_fields(db_session: AsyncSession) -> None:
    """Test UserIdentity model has user_id, provider_id, and external_id fields."""
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create identity with all required fields
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="external_123",
        username="external_user",
    )
    db_session.add(identity)
    await db_session.commit()
    await db_session.refresh(identity)

    # Verify all required fields exist
    assert identity.user_id == user.id
    assert identity.provider_id == provider.id
    assert identity.external_id == "external_123"
    assert identity.username == "external_user"


@pytest.mark.asyncio
async def test_user_identity_foreign_key_to_user_works(db_session: AsyncSession) -> None:
    """Test UserIdentity has a working foreign key relationship to User."""
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="ext123",
        username="testuser",
    )
    db_session.add(identity)
    await db_session.commit()

    # Re-query with joinedload to eager-load the user relationship
    result = await db_session.execute(
        select(UserIdentity)
        .where(UserIdentity.id == identity.id)
        .options(joinedload(UserIdentity.user))
    )
    loaded_identity = result.unique().scalar_one()

    # Verify foreign key relationship works
    assert loaded_identity.user is not None
    assert loaded_identity.user.username == "testuser"
    assert loaded_identity.user_id == user.id


@pytest.mark.asyncio
async def test_multiple_identities_per_user_supported(db_session: AsyncSession) -> None:
    """Test that a single user can have multiple provider identities."""
    t3k = OAuthProvider(name="t3k", enabled=True)
    google = OAuthProvider(name="google", enabled=True)
    db_session.add_all([t3k, google])
    await db_session.commit()

    user = User(username="multiuser", email="multi@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity_t3k = UserIdentity(
        user_id=user.id,
        provider_id=t3k.id,
        external_id="t3k_999",
        username="t3k_user",
    )
    identity_google = UserIdentity(
        user_id=user.id,
        provider_id=google.id,
        external_id="google_888",
        username="google_user",
    )
    db_session.add_all([identity_t3k, identity_google])
    await db_session.commit()

    # Query user's identities
    result = await db_session.execute(
        select(UserIdentity).where(UserIdentity.user_id == user.id)
    )
    identities = result.scalars().all()

    # Verify user has both identities
    assert len(identities) == 2
    external_ids = {identity.external_id for identity in identities}
    assert external_ids == {"t3k_999", "google_888"}
