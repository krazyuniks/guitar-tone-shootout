"""SQLAlchemy implementation of UserRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity as UserIdentityVO
from webapp.adapters.persistence.models.user import (
    OAuthProvider,
    User,
    UserIdentity,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyUserRepository:
    """SQLAlchemy implementation of UserRepository protocol.

    Maps between domain User entities and ORM User models, handling
    identity relationships and provider lookups.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, user_id: UUID) -> UserEntity | None:
        """Get a user by their ID.

        Args:
            user_id: The user's UUID

        Returns:
            The User entity if found, None otherwise
        """
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(joinedload(User.identities).joinedload(UserIdentity.provider))
        )
        result = await self.session.execute(stmt)
        user = result.unique().scalar_one_or_none()
        return self._to_entity(user) if user else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        """Get a user by email address.

        Args:
            email: The email address

        Returns:
            The User entity if found, None otherwise
        """
        stmt = (
            select(User)
            .where(User.email == email)
            .options(joinedload(User.identities).joinedload(UserIdentity.provider))
        )
        result = await self.session.execute(stmt)
        user = result.unique().scalar_one_or_none()
        return self._to_entity(user) if user else None

    async def get_by_identity(
        self,
        provider: str,
        external_id: str,
    ) -> UserEntity | None:
        """Get a user by an external identity.

        Args:
            provider: The identity provider name
            external_id: The ID from the external provider

        Returns:
            The User entity if found, None otherwise
        """
        # First get the provider
        provider_stmt = select(OAuthProvider).where(OAuthProvider.name == provider)
        provider_result = await self.session.execute(provider_stmt)
        provider_obj = provider_result.scalar_one_or_none()

        if not provider_obj:
            return None

        # Then find the identity
        stmt = (
            select(User)
            .join(UserIdentity, User.id == UserIdentity.user_id)
            .where(
                UserIdentity.provider_id == provider_obj.id,
                UserIdentity.external_id == external_id,
            )
            .options(joinedload(User.identities).joinedload(UserIdentity.provider))
        )
        result = await self.session.execute(stmt)
        user = result.unique().scalar_one_or_none()
        return self._to_entity(user) if user else None

    async def save(self, user: UserEntity) -> None:
        """Save a user (create or update).

        Args:
            user: The user entity to save
        """
        # Check if user exists
        existing = await self.session.get(User, user.id)

        if existing:
            # Update existing user
            existing.username = user.username
            existing.email = user.email
            existing.avatar_url = user.avatar_url
            existing.updated_at = user.updated_at

            # Update identities
            # Remove old identities not in the new list
            new_providers = {identity.provider for identity in user.identities}
            identities_to_delete = [
                identity
                for identity in existing.identities
                if identity.provider.name not in new_providers
            ]
            for identity in identities_to_delete:
                await self.session.delete(identity)
            if identities_to_delete:
                await self.session.flush()
                # Refresh to get updated identities list
                await self.session.refresh(existing, ["identities"])

            # Add or update identities
            for identity_vo in user.identities:
                # Get provider
                provider_stmt = select(OAuthProvider).where(
                    OAuthProvider.name == identity_vo.provider
                )
                provider_result = await self.session.execute(provider_stmt)
                provider_obj = provider_result.scalar_one_or_none()

                if not provider_obj:
                    # Create provider if it doesn't exist
                    provider_obj = OAuthProvider(
                        name=identity_vo.provider, enabled=True
                    )
                    self.session.add(provider_obj)
                    await self.session.flush()

                # Find or create identity
                existing_identity = None
                for ident in existing.identities:
                    if ident.provider.name == identity_vo.provider:
                        existing_identity = ident
                        break

                if existing_identity:
                    # Update existing identity
                    existing_identity.external_id = identity_vo.external_id
                    existing_identity.username = identity_vo.username
                    existing_identity.avatar_url = identity_vo.avatar_url
                else:
                    # Create new identity
                    new_identity = UserIdentity(
                        user_id=user.id,
                        provider_id=provider_obj.id,
                        external_id=identity_vo.external_id,
                        username=identity_vo.username,
                        avatar_url=identity_vo.avatar_url,
                    )
                    self.session.add(new_identity)
        else:
            # Create new user
            new_user = User(
                id=user.id,
                username=user.username,
                email=user.email,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            self.session.add(new_user)
            await self.session.flush()

            # Add identities
            for identity_vo in user.identities:
                # Get or create provider
                provider_stmt = select(OAuthProvider).where(
                    OAuthProvider.name == identity_vo.provider
                )
                provider_result = await self.session.execute(provider_stmt)
                provider_obj = provider_result.scalar_one_or_none()

                if not provider_obj:
                    provider_obj = OAuthProvider(
                        name=identity_vo.provider, enabled=True
                    )
                    self.session.add(provider_obj)
                    await self.session.flush()

                # Create identity
                new_identity = UserIdentity(
                    user_id=user.id,
                    provider_id=provider_obj.id,
                    external_id=identity_vo.external_id,
                    username=identity_vo.username,
                    avatar_url=identity_vo.avatar_url,
                )
                self.session.add(new_identity)

        await self.session.flush()

    async def delete(self, user_id: UUID) -> None:
        """Delete a user by ID.

        Args:
            user_id: The user's UUID
        """
        user = await self.session.get(User, user_id)
        if user:
            await self.session.delete(user)
            await self.session.flush()

    def _to_entity(self, user: User) -> UserEntity:
        """Convert ORM User to domain UserEntity.

        Args:
            user: The ORM User model

        Returns:
            The domain UserEntity
        """
        identities = [
            UserIdentityVO(
                provider=identity.provider.name,
                external_id=identity.external_id,
                username=identity.username,
                avatar_url=identity.avatar_url,
            )
            for identity in user.identities
        ]

        return UserEntity(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            identities=identities,
            is_active=True,  # ORM model doesn't have is_active yet
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
