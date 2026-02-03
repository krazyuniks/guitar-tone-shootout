"""User ORM models for persistence layer."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class OAuthProvider(UUIDMixin, Base):
    """OAuth provider model.

    Represents available OAuth providers (t3k, google, etc.) that users
    can authenticate with. Providers can be enabled or disabled.

    Attributes:
        id: Primary key (UUIDv7)
        name: Provider name (e.g., 't3k', 'google')
        enabled: Whether this provider is currently active
    """

    __tablename__ = "oauth_providers"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationship to identities
    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity",
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class User(UUIDMixin, TimestampMixin, Base):
    """User model for authenticated users.

    Users are the core entity for authentication and authorization.
    They can be linked to multiple external identity providers.

    Attributes:
        id: Primary key (UUIDv7)
        username: Display name
        email: Email address (optional, indexed)
        avatar_url: Profile image URL (optional)
        created_at: When the user was created
        updated_at: When the user was last updated
        identities: List of linked external identities
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationship to identities
    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load identities by default
    )

    # TODO: Add relationships to Gear, DITrack, SignalChain, Shootout, Job once those models exist


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
    user: Mapped["User"] = relationship("User", back_populates="identities")
    provider: Mapped["OAuthProvider"] = relationship(
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
