"""Unit tests for UserIdentity ORM model extraction (T8).

This task extracts UserIdentity into its own module file.
Tests verify the model can be imported from user_identity.py.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.user import OAuthProvider, User

# This import MUST work after T8 implementation
from webapp.adapters.persistence.models.user_identity import UserIdentity


async def test_user_identity_importable_from_user_identity_module(
    db_session: AsyncSession,
) -> None:
    """Test UserIdentity can be imported from user_identity.py module."""
    # If this test runs, the import at the top succeeded
    # Now verify the model works with the database
    provider = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create identity using the imported UserIdentity
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id=f"external_{uuid.uuid4().hex[:8]}",
        username=f"external_user_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(identity)
    await db_session.commit()
    await db_session.refresh(identity)

    # Verify it persisted correctly
    assert identity.id is not None
    assert isinstance(identity.id, uuid.UUID)
    assert identity.user_id == user.id
    assert identity.provider_id == provider.id


async def test_user_identity_has_all_required_fields(db_session: AsyncSession) -> None:
    """Test UserIdentity model has user_id, provider_id, and external_id fields."""
    provider = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create identity with all required fields
    ext_id = f"external_{uuid.uuid4().hex[:8]}"
    ext_user = f"external_user_{uuid.uuid4().hex[:8]}"
    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id=ext_id,
        username=ext_user,
    )
    db_session.add(identity)
    await db_session.commit()
    await db_session.refresh(identity)

    # Verify all required fields exist
    assert identity.user_id == user.id
    assert identity.provider_id == provider.id
    assert identity.external_id == ext_id
    assert identity.username == ext_user


async def test_user_identity_foreign_key_to_user_works(db_session: AsyncSession) -> None:
    """Test UserIdentity has a working foreign key relationship to User."""
    provider = OAuthProvider(name=f"provider_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    username = f"testuser_{uuid.uuid4().hex[:8]}"
    user = User(username=username, email=f"{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity = UserIdentity(
        user_id=user.id,
        provider_id=provider.id,
        external_id=f"ext_{uuid.uuid4().hex[:8]}",
        username=f"testuser_{uuid.uuid4().hex[:8]}",
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
    assert loaded_identity.user.username == username
    assert loaded_identity.user_id == user.id


async def test_multiple_identities_per_user_supported(db_session: AsyncSession) -> None:
    """Test that a single user can have multiple provider identities."""
    t3k = OAuthProvider(name=f"t3k_{uuid.uuid4().hex[:8]}", enabled=True)
    google = OAuthProvider(name=f"google_{uuid.uuid4().hex[:8]}", enabled=True)
    db_session.add_all([t3k, google])
    await db_session.commit()

    user = User(
        username=f"multiuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    identity_t3k = UserIdentity(
        user_id=user.id,
        provider_id=t3k.id,
        external_id=f"t3k_{uuid.uuid4().hex[:8]}",
        username=f"t3k_user_{uuid.uuid4().hex[:8]}",
    )
    identity_google = UserIdentity(
        user_id=user.id,
        provider_id=google.id,
        external_id=f"google_{uuid.uuid4().hex[:8]}",
        username=f"google_user_{uuid.uuid4().hex[:8]}",
    )
    db_session.add_all([identity_t3k, identity_google])
    await db_session.commit()

    # Query user's identities
    result = await db_session.execute(select(UserIdentity).where(UserIdentity.user_id == user.id))
    identities = result.scalars().all()

    # Verify user has both identities
    assert len(identities) == 2
    external_ids = {identity.external_id for identity in identities}
    assert identity_t3k.external_id in external_ids
    assert identity_google.external_id in external_ids
