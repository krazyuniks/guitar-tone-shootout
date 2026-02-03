"""User entity for domain layer."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow


@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Value object representing an external identity link.

    Users can have multiple external identities (T3K, Google, etc.)
    without the core domain knowing the specifics of each provider.

    Attributes:
        provider: Identity provider name (e.g., 't3k', 'google')
        external_id: ID from the external provider
        username: Display name from the provider
        avatar_url: Profile image URL (optional)
    """

    provider: str
    external_id: str
    username: str
    avatar_url: str | None = None


@dataclass(eq=False, slots=True)
class User(Entity):
    """Domain entity representing an authenticated user.

    Users are identified by their internal UUID and can be linked
    to multiple external identity providers via UserIdentity.

    Attributes:
        id: Unique internal identifier
        username: Primary display name
        email: User's email address (optional)
        avatar_url: Profile image URL (optional)
        identities: List of external identity links
        is_active: Whether the account is active
        created_at: When the user was created
        updated_at: When the user was last updated
    """

    username: str = ""
    email: str | None = None
    avatar_url: str | None = None
    identities: list[UserIdentity] = field(default_factory=list)
    is_active: bool = True
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def add_identity(self, identity: UserIdentity) -> None:
        """Add an external identity link.

        Args:
            identity: The identity to add

        Raises:
            ValueError: If an identity from this provider already exists
        """
        for existing in self.identities:
            if existing.provider == identity.provider:
                raise ValueError(
                    f"Identity for provider '{identity.provider}' already exists"
                )
        self.identities.append(identity)
        self.updated_at = utcnow()

    def get_identity(self, provider: str) -> UserIdentity | None:
        """Get the identity for a specific provider.

        Args:
            provider: The provider name to look up

        Returns:
            The UserIdentity if found, None otherwise
        """
        for identity in self.identities:
            if identity.provider == provider:
                return identity
        return None

    def remove_identity(self, provider: str) -> bool:
        """Remove an identity link.

        Args:
            provider: The provider to remove

        Returns:
            True if removed, False if not found
        """
        for i, identity in enumerate(self.identities):
            if identity.provider == provider:
                self.identities.pop(i)
                self.updated_at = utcnow()
                return True
        return False

    def update_username(self, username: str) -> None:
        """Update the username.

        Args:
            username: New username
        """
        self.username = username
        self.updated_at = utcnow()

    def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
        self.updated_at = utcnow()

    def activate(self) -> None:
        """Activate the user account."""
        self.is_active = True
        self.updated_at = utcnow()

    @classmethod
    def create_with_identity(
        cls,
        identity: UserIdentity,
        email: str | None = None,
    ) -> "User":
        """Create a new user from an external identity.

        Args:
            identity: The external identity
            email: Optional email address

        Returns:
            A new User instance
        """
        user = cls(
            username=identity.username,
            email=email,
            avatar_url=identity.avatar_url,
        )
        user.identities.append(identity)
        return user
