from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin
from .user_identity import UserIdentity  # Re-export for backwards compatibility

__all__ = ["OAuthProvider", "User", "UserIdentity"]

if TYPE_CHECKING:
    from .job import Job
    from .notification import UserNotification
    from .shootout import DITrack, Shootout
    from .signal_chain import SignalChain, SignalChainGroup
    from .tag import Tag
    from .user_gear import UserGear


class OAuthProvider(UUIDMixin, Base):
    """OAuth provider model.

    Represents available OAuth providers (t3k, google, etc.) that users
    can authenticate with. Providers can be enabled or disabled.

    Attributes:
        id: Primary key (UUIDv7)
        name: Provider name (e.g., 't3k', 'google')
        client_id: OAuth client ID for this provider
        client_secret: OAuth client secret for this provider
        enabled: Whether this provider is currently active
    """

    __tablename__ = "oauth_providers"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationship to identities
    identities: Mapped[list[UserIdentity]] = relationship(
        "UserIdentity",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="raise",
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
        is_active: Whether the user account is active
        created_at: When the user was created
        updated_at: When the user was last updated
        identities: List of linked external identities
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationship to identities
    identities: Mapped[list[UserIdentity]] = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationships to signal chains
    signal_chains: Mapped[list[SignalChain]] = relationship(
        "SignalChain",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    signal_chain_groups: Mapped[list[SignalChainGroup]] = relationship(
        "SignalChainGroup",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationships to DI tracks and shootouts
    di_tracks: Mapped[list[DITrack]] = relationship(
        "DITrack",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    shootouts: Mapped[list[Shootout]] = relationship(
        "Shootout",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationship to jobs
    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationship to user gear library
    user_gear: Mapped[list[UserGear]] = relationship(
        "UserGear",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationship to notifications
    notifications: Mapped[list[UserNotification]] = relationship(
        "UserNotification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Relationship to tags
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
