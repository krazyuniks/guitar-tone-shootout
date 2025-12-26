"""User model for storing Tone 3000 authenticated users."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """User model representing authenticated Tone 3000 users.

    Stores user profile data from Tone 3000 OAuth and manages their
    API access tokens for making requests to the Tone 3000 API.
    """

    __tablename__ = "users"

    # Tone 3000 profile data (UUID string from Tone 3000)
    tone3000_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # OAuth tokens (encrypted in production via application layer)
    access_token: Mapped[str | None] = mapped_column(String(2000))
    refresh_token: Mapped[str | None] = mapped_column(String(2000))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Return string representation of the user."""
        return f"<User {self.username} (tone3000_id={self.tone3000_id})>"
