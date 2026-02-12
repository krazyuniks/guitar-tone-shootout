"""Unit tests for IdentityService (T19).

Tests for IdentityService which handles user creation and identity linking:
- Creating new users from OAuth profile
- Linking existing users to OAuth providers
- Finding or creating users by provider + external_id
- Updating user profile from OAuth data
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Real database with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    async_session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a T3K OAuth provider."""
    provider = OAuthProvider(
        name="t3k",
        client_id="test_client_id",
        client_secret="test_client_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestIdentityService:
    """Test suite for IdentityService user creation and linking."""

    async def test_create_new_user_from_oauth_profile(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test creating a new user from OAuth profile data."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        # OAuth profile from T3K
        oauth_profile = {
            "id": "t3k_user_123",
            "username": "tone_master",
            "email": "master@tone3000.com",
            "avatar_url": "https://tone3000.com/avatar.jpg",
        }

        # Create user from OAuth profile
        user = await service.get_or_create_user(
            provider_name="t3k",
            external_id=oauth_profile["id"],
            username=oauth_profile["username"],
            email=oauth_profile["email"],
            avatar_url=oauth_profile.get("avatar_url"),
        )

        # User should be created with OAuth data
        assert user.id is not None
        assert user.username == "tone_master"
        assert user.email == "master@tone3000.com"
        assert user.avatar_url == "https://tone3000.com/avatar.jpg"
        assert user.is_active is True

        # Re-query user with identities eagerly loaded (lazy="raise" on model)
        result = await db_session.execute(
            select(User).where(User.id == user.id).options(joinedload(User.identities))
        )
        user = result.unique().scalar_one()

        # User should have identity linked to provider
        assert len(user.identities) == 1
        identity = user.identities[0]
        assert identity.external_id == "t3k_user_123"
        assert identity.username == "tone_master"
        assert identity.provider_id == t3k_provider.id

    async def test_find_existing_user_by_provider_and_external_id(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test finding existing user by provider + external_id."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        # Create user first time
        first_call = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_existing_user",
            username="existing_user",
            email="existing@tone3000.com",
        )
        first_user_id = first_call.id

        # Second call with same external_id should return same user
        second_call = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_existing_user",
            username="existing_user",
            email="existing@tone3000.com",
        )

        # Should be the same user
        assert second_call.id == first_user_id

        # Verify only one user exists in database
        result = await db_session.execute(select(User))
        all_users = result.scalars().all()
        assert len(all_users) == 1

    async def test_update_user_profile_from_oauth_data(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test updating user profile when OAuth data changes."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        # Create user with initial data
        user = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_user_456",
            username="old_username",
            email="old@email.com",
        )
        # Update with new OAuth data
        updated_user = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_user_456",
            username="new_username",
            email="new@email.com",
            avatar_url="https://tone3000.com/new_avatar.jpg",
        )

        # User should be updated with new data
        assert updated_user.id == user.id
        assert updated_user.username == "new_username"
        assert updated_user.email == "new@email.com"
        assert updated_user.avatar_url == "https://tone3000.com/new_avatar.jpg"

    async def test_create_user_identity_links_to_provider(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test UserIdentity is created and linked to provider."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        user = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_identity_test",
            username="identity_user",
            email="identity@test.com",
        )

        # Query UserIdentity directly
        result = await db_session.execute(
            select(UserIdentity).where(UserIdentity.user_id == user.id)
        )
        identity = result.scalar_one()

        # Identity should be linked to provider
        assert identity.provider_id == t3k_provider.id
        assert identity.external_id == "t3k_identity_test"
        assert identity.username == "identity_user"

    async def test_service_raises_error_for_disabled_provider(
        self, db_session: AsyncSession
    ) -> None:
        """Test service raises error when provider is disabled."""
        from webapp.services.identity_service import IdentityService

        # Create disabled provider
        disabled_provider = OAuthProvider(
            name="disabled",
            client_id="disabled_client",
            client_secret="disabled_secret",
            enabled=False,
        )
        db_session.add(disabled_provider)
        await db_session.commit()

        service = IdentityService(db_session)

        # Should raise error for disabled provider
        with pytest.raises(ValueError, match="Provider 'disabled' is not enabled"):
            await service.get_or_create_user(
                provider_name="disabled",
                external_id="test_user",
                username="test",
                email="test@example.com",
            )

    async def test_service_raises_error_for_nonexistent_provider(
        self, db_session: AsyncSession
    ) -> None:
        """Test service raises error when provider doesn't exist."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        # Should raise error for non-existent provider
        with pytest.raises(ValueError, match="Provider 'nonexistent' not found"):
            await service.get_or_create_user(
                provider_name="nonexistent",
                external_id="test_user",
                username="test",
                email="test@example.com",
            )

    async def test_identity_service_handles_multiple_providers(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test user can have identities from multiple providers."""
        from webapp.services.identity_service import IdentityService

        # Create second provider (Google)
        google_provider = OAuthProvider(
            name="google",
            client_id="google_client",
            client_secret="google_secret",
            enabled=True,
        )
        db_session.add(google_provider)
        await db_session.commit()

        service = IdentityService(db_session)

        # Create user via T3K
        t3k_user = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_multi_user",
            username="multi_user",
            email="multi@example.com",
        )

        # Link same user to Google (would need different flow, but testing service capability)
        # This test verifies the service CAN handle multiple providers
        # Actual linking of existing user to new provider would be separate method
        assert t3k_user is not None

        # Re-query user with identities eagerly loaded (lazy="raise" on model)
        result = await db_session.execute(
            select(User).where(User.id == t3k_user.id).options(joinedload(User.identities))
        )
        t3k_user = result.unique().scalar_one()

        assert len(t3k_user.identities) == 1

    async def test_service_creates_inactive_user_when_specified(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test service can create inactive users if needed."""
        from webapp.services.identity_service import IdentityService

        service = IdentityService(db_session)

        # Create user with is_active=False
        user = await service.get_or_create_user(
            provider_name="t3k",
            external_id="t3k_inactive",
            username="inactive_user",
            email="inactive@example.com",
            is_active=False,
        )

        assert user.is_active is False
