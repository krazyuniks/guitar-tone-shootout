"""Unit tests for OAuthProvider ORM model (T7).

Tests for OAuthProvider configuration model that stores OAuth provider
configuration including client_id, client_secret, and endpoints.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider


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
async def test_oauth_provider_creates_with_required_fields(db_session: AsyncSession) -> None:
    """Test OAuthProvider model creates with all required fields."""
    provider = OAuthProvider(
        name="t3k",
        client_id="test_client_id_123",
        client_secret="test_secret_abc",
        enabled=True,
    )

    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    # Verify all fields
    assert provider.id is not None
    assert isinstance(provider.id, uuid.UUID)
    assert provider.name == "t3k"
    assert provider.client_id == "test_client_id_123"
    assert provider.client_secret == "test_secret_abc"
    assert provider.enabled is True


@pytest.mark.asyncio
async def test_oauth_provider_name_is_unique(db_session: AsyncSession) -> None:
    """Test OAuthProvider name field enforces uniqueness."""
    provider1 = OAuthProvider(
        name="t3k",
        client_id="client1",
        client_secret="secret1",
        enabled=True,
    )
    db_session.add(provider1)
    await db_session.commit()

    # Attempt to create second provider with same name
    provider2 = OAuthProvider(
        name="t3k",
        client_id="client2",
        client_secret="secret2",
        enabled=True,
    )
    db_session.add(provider2)

    # Should raise integrity error due to unique constraint
    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_oauth_provider_enabled_defaults_to_true(db_session: AsyncSession) -> None:
    """Test OAuthProvider enabled field defaults to True."""
    provider = OAuthProvider(
        name="google",
        client_id="google_client",
        client_secret="google_secret",
        # Note: not setting enabled explicitly
    )

    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.enabled is True


@pytest.mark.asyncio
async def test_oauth_provider_can_be_disabled(db_session: AsyncSession) -> None:
    """Test OAuthProvider can be disabled."""
    provider = OAuthProvider(
        name="facebook",
        client_id="fb_client",
        client_secret="fb_secret",
        enabled=False,
    )

    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.enabled is False


@pytest.mark.asyncio
async def test_oauth_provider_supports_multiple_providers(db_session: AsyncSession) -> None:
    """Test multiple OAuth providers can exist (T3K, Google, GitHub, Facebook)."""
    providers = [
        OAuthProvider(
            name="t3k",
            client_id="t3k_client",
            client_secret="t3k_secret",
            enabled=True,
        ),
        OAuthProvider(
            name="google",
            client_id="google_client",
            client_secret="google_secret",
            enabled=True,
        ),
        OAuthProvider(
            name="github",
            client_id="github_client",
            client_secret="github_secret",
            enabled=False,  # Stub/disabled
        ),
        OAuthProvider(
            name="facebook",
            client_id="facebook_client",
            client_secret="facebook_secret",
            enabled=False,  # Stub/disabled
        ),
    ]

    db_session.add_all(providers)
    await db_session.commit()

    # Query all providers
    result = await db_session.execute(select(OAuthProvider))
    all_providers = result.scalars().all()

    assert len(all_providers) == 4
    provider_names = {p.name for p in all_providers}
    assert provider_names == {"t3k", "google", "github", "facebook"}


@pytest.mark.asyncio
async def test_oauth_provider_query_by_name(db_session: AsyncSession) -> None:
    """Test querying OAuthProvider by name."""
    provider = OAuthProvider(
        name="t3k",
        client_id="t3k_client",
        client_secret="t3k_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()

    # Query by name
    result = await db_session.execute(select(OAuthProvider).where(OAuthProvider.name == "t3k"))
    found = result.scalar_one()

    assert found.name == "t3k"
    assert found.client_id == "t3k_client"


@pytest.mark.asyncio
async def test_oauth_provider_query_enabled_only(db_session: AsyncSession) -> None:
    """Test querying only enabled OAuth providers."""
    providers = [
        OAuthProvider(name="t3k", client_id="c1", client_secret="s1", enabled=True),
        OAuthProvider(name="google", client_id="c2", client_secret="s2", enabled=True),
        OAuthProvider(name="github", client_id="c3", client_secret="s3", enabled=False),
    ]
    db_session.add_all(providers)
    await db_session.commit()

    # Query only enabled providers
    result = await db_session.execute(
        select(OAuthProvider).where(OAuthProvider.enabled == True)  # noqa: E712
    )
    enabled_providers = result.scalars().all()

    assert len(enabled_providers) == 2
    enabled_names = {p.name for p in enabled_providers}
    assert enabled_names == {"t3k", "google"}


@pytest.mark.asyncio
async def test_oauth_provider_client_secret_is_stored(db_session: AsyncSession) -> None:
    """Test OAuthProvider stores client_secret securely.

    Note: In production, client_secret should be encrypted.
    This test verifies the field exists and can be stored/retrieved.
    """
    provider = OAuthProvider(
        name="t3k",
        client_id="test_client",
        client_secret="very_secret_value_abc123",
        enabled=True,
    )

    db_session.add(provider)
    await db_session.commit()

    # Store ID for fresh query
    provider_id = provider.id

    # Close and reopen session to ensure persistence
    await db_session.close()

    # Create new session
    async_session = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    new_session = async_session()

    # Query back and verify secret is persisted
    result = await new_session.execute(select(OAuthProvider).where(OAuthProvider.id == provider_id))
    loaded_provider = result.scalar_one()

    assert loaded_provider.client_secret == "very_secret_value_abc123"
    await new_session.close()


@pytest.mark.asyncio
async def test_oauth_provider_update_enabled_status(db_session: AsyncSession) -> None:
    """Test OAuthProvider enabled status can be toggled."""
    provider = OAuthProvider(
        name="github",
        client_id="github_client",
        client_secret="github_secret",
        enabled=False,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    # Initially disabled
    assert provider.enabled is False

    # Enable the provider
    provider.enabled = True
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.enabled is True


@pytest.mark.asyncio
async def test_oauth_provider_cascade_deletes_identities(db_session: AsyncSession) -> None:
    """Test deleting OAuthProvider cascades to UserIdentity records.

    This test verifies the relationship cascade behavior defined in the model.
    """
    from webapp.adapters.persistence.models.user import User, UserIdentity

    # Create provider
    provider = OAuthProvider(
        name="t3k",
        client_id="t3k_client",
        client_secret="t3k_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()

    # Create user
    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    # Create identity linking user and provider
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="external_123",
        username="external_user",
    )
    db_session.add(identity)
    await db_session.commit()

    # Verify identity exists
    result = await db_session.execute(select(UserIdentity))
    identities = result.scalars().all()
    assert len(identities) == 1

    # Delete provider
    await db_session.delete(provider)
    await db_session.commit()

    # Verify identity was cascade deleted
    result = await db_session.execute(select(UserIdentity))
    identities = result.scalars().all()
    assert len(identities) == 0
