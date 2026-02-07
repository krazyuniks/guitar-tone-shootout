"""Identity service for user creation and OAuth identity linking.

Handles creating users from OAuth profiles and linking existing users
to external identity providers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity


class IdentityService:
    """Service for managing user identities and OAuth provider links.

    Responsibilities:
    - Creating new users from OAuth profile data
    - Finding existing users by provider + external_id
    - Updating user profiles from OAuth data
    - Linking users to OAuth providers via UserIdentity
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize identity service.

        Args:
            db_session: Database session for queries and transactions
        """
        self.db_session = db_session

    async def get_or_create_user(
        self,
        provider_name: str,
        external_id: str,
        username: str,
        email: str | None = None,
        avatar_url: str | None = None,
        is_active: bool = True,
    ) -> User:
        """Get existing user or create new user from OAuth profile.

        Looks up user by provider + external_id. If found, updates profile
        with latest OAuth data. If not found, creates new user and identity.

        Args:
            provider_name: OAuth provider name (e.g., 't3k', 'google')
            external_id: User ID from external provider
            username: Display name from OAuth provider
            email: Email address from OAuth provider (optional)
            avatar_url: Profile image URL from provider (optional)
            is_active: Whether user account should be active (default True)

        Returns:
            User instance (new or existing)

        Raises:
            ValueError: If provider not found or disabled
        """
        # Single query: identity JOIN user JOIN provider
        # Fetches everything needed in one round-trip
        result = await self.db_session.execute(
            select(UserIdentity)
            .options(joinedload(UserIdentity.user))
            .join(UserIdentity.provider)
            .where(OAuthProvider.name == provider_name)
            .where(UserIdentity.external_id == external_id)
        )
        identity = result.unique().scalar_one_or_none()

        if identity is not None:
            # User exists — update profile with latest OAuth data
            user = identity.user
            user.username = username
            user.email = email
            user.avatar_url = avatar_url
            identity.username = username
            identity.avatar_url = avatar_url

            await self.db_session.commit()
            return user

        # New user — need provider for the identity link
        provider = await self._get_provider(provider_name)

        user = User(
            username=username,
            email=email,
            avatar_url=avatar_url,
            is_active=is_active,
        )
        self.db_session.add(user)
        await self.db_session.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider_id=provider.id,
            external_id=external_id,
            username=username,
            avatar_url=avatar_url,
        )
        self.db_session.add(identity)

        await self.db_session.commit()
        return user

    async def _get_provider(self, provider_name: str) -> OAuthProvider:
        """Fetch OAuth provider from database, auto-creating T3K if missing.

        T3K uses api_key flow and doesn't need client_id/client_secret,
        so we auto-create the row on first login rather than requiring
        a migration or manual seed.

        Args:
            provider_name: Name of provider to fetch

        Returns:
            OAuthProvider instance

        Raises:
            ValueError: If provider not found or disabled
        """
        result = await self.db_session.execute(
            select(OAuthProvider).where(OAuthProvider.name == provider_name)
        )
        provider = result.scalar_one_or_none()

        if provider is None:
            if provider_name == "t3k":
                provider = OAuthProvider(name="t3k", enabled=True)
                self.db_session.add(provider)
                await self.db_session.flush()
            else:
                raise ValueError(f"Provider '{provider_name}' not found")

        if not provider.enabled:
            raise ValueError(f"Provider '{provider_name}' is not enabled")

        return provider
