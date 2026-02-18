"""Unit tests for OAuthProvider ORM model (T7).

Tests for OAuthProvider configuration model that stores OAuth provider
configuration including client_id, client_secret, and endpoints.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from webapp.adapters.persistence.models.user import OAuthProvider


async def test_oauth_provider_creates_with_required_fields(db_session: AsyncSession) -> None:
    """Test OAuthProvider model creates with all required fields."""
    suffix = uuid.uuid4().hex[:8]
    provider = OAuthProvider(
        name=f"provider_{suffix}",
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
    assert provider.name == f"provider_{suffix}"
    assert provider.client_id == "test_client_id_123"
    assert provider.client_secret == "test_secret_abc"
    assert provider.enabled is True


async def test_oauth_provider_name_is_unique(db_session: AsyncSession) -> None:
    """Test OAuthProvider name field enforces uniqueness."""
    shared_name = f"provider_{uuid.uuid4().hex[:8]}"
    provider1 = OAuthProvider(
        name=shared_name,
        client_id="client1",
        client_secret="secret1",
        enabled=True,
    )
    db_session.add(provider1)
    await db_session.commit()

    # Attempt to create second provider with same name
    provider2 = OAuthProvider(
        name=shared_name,
        client_id="client2",
        client_secret="secret2",
        enabled=True,
    )
    db_session.add(provider2)

    # Should raise integrity error due to unique constraint
    import pytest

    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        await db_session.commit()


async def test_oauth_provider_enabled_defaults_to_true(db_session: AsyncSession) -> None:
    """Test OAuthProvider enabled field defaults to True."""
    provider = OAuthProvider(
        name=f"provider_{uuid.uuid4().hex[:8]}",
        client_id="google_client",
        client_secret="google_secret",
        # Note: not setting enabled explicitly
    )

    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.enabled is True


async def test_oauth_provider_can_be_disabled(db_session: AsyncSession) -> None:
    """Test OAuthProvider can be disabled."""
    provider = OAuthProvider(
        name=f"provider_{uuid.uuid4().hex[:8]}",
        client_id="fb_client",
        client_secret="fb_secret",
        enabled=False,
    )

    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.enabled is False


async def test_oauth_provider_supports_multiple_providers(db_session: AsyncSession) -> None:
    """Test multiple OAuth providers can exist."""
    suffix = uuid.uuid4().hex[:8]
    providers = [
        OAuthProvider(
            name=f"t3k_{suffix}",
            client_id="t3k_client",
            client_secret="t3k_secret",
            enabled=True,
        ),
        OAuthProvider(
            name=f"google_{suffix}",
            client_id="google_client",
            client_secret="google_secret",
            enabled=True,
        ),
        OAuthProvider(
            name=f"github_{suffix}",
            client_id="github_client",
            client_secret="github_secret",
            enabled=False,
        ),
        OAuthProvider(
            name=f"facebook_{suffix}",
            client_id="facebook_client",
            client_secret="facebook_secret",
            enabled=False,
        ),
    ]

    db_session.add_all(providers)
    await db_session.commit()

    # Query providers created in this test
    result = await db_session.execute(
        select(OAuthProvider).where(OAuthProvider.name.like(f"%{suffix}"))
    )
    all_providers = result.scalars().all()

    assert len(all_providers) == 4
    provider_names = {p.name for p in all_providers}
    assert provider_names == {
        f"t3k_{suffix}",
        f"google_{suffix}",
        f"github_{suffix}",
        f"facebook_{suffix}",
    }


async def test_oauth_provider_query_by_name(db_session: AsyncSession) -> None:
    """Test querying OAuthProvider by name."""
    name = f"provider_{uuid.uuid4().hex[:8]}"
    provider = OAuthProvider(
        name=name,
        client_id="t3k_client",
        client_secret="t3k_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()

    # Query by name
    result = await db_session.execute(select(OAuthProvider).where(OAuthProvider.name == name))
    found = result.scalar_one()

    assert found.name == name
    assert found.client_id == "t3k_client"


async def test_oauth_provider_query_enabled_only(db_session: AsyncSession) -> None:
    """Test querying only enabled OAuth providers."""
    suffix = uuid.uuid4().hex[:8]
    providers = [
        OAuthProvider(name=f"t3k_{suffix}", client_id="c1", client_secret="s1", enabled=True),
        OAuthProvider(name=f"google_{suffix}", client_id="c2", client_secret="s2", enabled=True),
        OAuthProvider(name=f"github_{suffix}", client_id="c3", client_secret="s3", enabled=False),
    ]
    db_session.add_all(providers)
    await db_session.commit()

    # Query only enabled providers created in this test
    result = await db_session.execute(
        select(OAuthProvider).where(
            OAuthProvider.enabled == True,  # noqa: E712
            OAuthProvider.name.like(f"%{suffix}"),
        )
    )
    enabled_providers = result.scalars().all()

    assert len(enabled_providers) == 2
    enabled_names = {p.name for p in enabled_providers}
    assert enabled_names == {f"t3k_{suffix}", f"google_{suffix}"}


async def test_oauth_provider_client_secret_is_stored(db_session: AsyncSession) -> None:
    """Test OAuthProvider stores client_secret securely.

    Note: In production, client_secret should be encrypted.
    This test verifies the field exists and can be stored/retrieved.
    """
    provider = OAuthProvider(
        name=f"provider_{uuid.uuid4().hex[:8]}",
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


async def test_oauth_provider_update_enabled_status(db_session: AsyncSession) -> None:
    """Test OAuthProvider enabled status can be toggled."""
    provider = OAuthProvider(
        name=f"provider_{uuid.uuid4().hex[:8]}",
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


async def test_oauth_provider_cascade_deletes_identities(db_session: AsyncSession) -> None:
    """Test deleting OAuthProvider cascades to UserIdentity records.

    This test verifies the relationship cascade behavior defined in the model.
    """
    from webapp.adapters.persistence.models.user import User, UserIdentity

    # Create provider
    provider = OAuthProvider(
        name=f"provider_{uuid.uuid4().hex[:8]}",
        client_id="t3k_client",
        client_secret="t3k_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()

    # Create user
    user = User(
        username=f"test_user_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    db_session.add(user)
    await db_session.commit()

    # Create identity linking user and provider
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id=f"external_{uuid.uuid4().hex[:8]}",
        username=f"external_user_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(identity)
    await db_session.commit()

    # Verify identity exists
    identity_id = identity.id
    result = await db_session.execute(select(UserIdentity).where(UserIdentity.id == identity_id))
    identities = result.scalars().all()
    assert len(identities) == 1

    # Delete provider
    await db_session.delete(provider)
    await db_session.commit()

    # Verify identity was cascade deleted
    result = await db_session.execute(select(UserIdentity).where(UserIdentity.id == identity_id))
    identities = result.scalars().all()
    assert len(identities) == 0
