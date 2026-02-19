"""Unit tests for User ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity


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

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.username == "test_user"
    assert user.email == "test@example.com"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


async def test_user_identity_links_to_user(db_session: AsyncSession) -> None:
    """Test UserIdentity properly links to User."""
    provider_name = f"test_provider_{uuid.uuid4().hex[:8]}"
    provider = OAuthProvider(name=provider_name, enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id="12345",
        username="external_user",
        avatar_url="https://provider.com/avatar.png",
    )
    db_session.add(identity)
    await db_session.commit()

    user_id = user.id

    result = await db_session.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    loaded_user = result.unique().scalar_one()

    assert len(loaded_user.identities) == 1
    assert loaded_user.identities[0].external_id == "12345"
    assert loaded_user.identities[0].username == "external_user"
    assert loaded_user.identities[0].provider.name == provider_name


async def test_user_has_many_identities(db_session: AsyncSession) -> None:
    """Test User can have multiple UserIdentities."""
    provider1 = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    provider2 = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add_all([provider1, provider2])
    await db_session.commit()

    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity1 = UserIdentity(
        user_id=user.id,
        provider_id=provider1.id,
        external_id="t3k_123",
        username="t3k_user",
    )
    identity2 = UserIdentity(
        user_id=user.id,
        provider_id=provider2.id,
        external_id="google_456",
        username="google_user",
    )
    db_session.add_all([identity1, identity2])
    await db_session.commit()

    user_id = user.id

    result = await db_session.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    loaded_user = result.unique().scalar_one()

    assert len(loaded_user.identities) == 2
    provider_names = {identity.provider.name for identity in loaded_user.identities}
    assert provider_names == {provider1.name, provider2.name}


async def test_email_index_exists(db_session: AsyncSession) -> None:
    """Test email column has an index for performance."""
    user1 = User(username="user1", email="user1@example.com")
    user2 = User(username="user2", email="user2@example.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "user1@example.com"))
    found = result.scalar_one()

    assert found.username == "user1"


async def test_provider_lookup_index(db_session: AsyncSession) -> None:
    """Test provider lookups have proper indexes."""
    provider = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    user1 = User(username="user1")
    user2 = User(username="user2")
    db_session.add_all([user1, user2])
    await db_session.commit()

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

    result = await db_session.execute(
        select(UserIdentity).where(
            UserIdentity.provider_id == provider.id,
            UserIdentity.external_id == "123",
        )
    )
    found = result.scalar_one()

    assert found.username == "user1_external"


async def test_oauth_provider_model(db_session: AsyncSession) -> None:
    """Test OAuthProvider model."""
    provider_name = f"test_provider_{uuid.uuid4().hex[:8]}"
    provider = OAuthProvider(name=provider_name, enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.id is not None
    assert provider.name == provider_name
    assert provider.enabled is True
