"""UserIdentity ORM model for linking users to external OAuth providers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .user import OAuthProvider, User


class UserIdentity(UUIDMixin, TimestampMixin, Base):
    """User identity model for linking external providers.

    Each UserIdentity represents a link between a User and an external
    OAuth provider. Users can have multiple identities (one per provider).

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        provider_id: Foreign key to oauth_providers table
        external_id: ID from the external provider
        username: Display name from the provider
        avatar_url: Profile image URL from provider (optional)
        created_at: When the identity link was created
        updated_at: When the identity was last updated
        user: Reference to the User
        provider: Reference to the OAuthProvider
    """

    __tablename__ = "user_identities"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("oauth_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="identities")
    provider: Mapped[OAuthProvider] = relationship(
        "OAuthProvider",
        back_populates="identities",
        lazy="selectin",  # Eager load provider by default
    )

    # Indexes for common query patterns
    __table_args__ = (
        # Composite index for provider + external_id lookups
        Index("ix_user_identities_provider_external", "provider_id", "external_id"),
        # Index for user_id lookups
        Index("ix_user_identities_user_id", "user_id"),
    )
