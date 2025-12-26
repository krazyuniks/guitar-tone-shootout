"""Authentication schemas for Tone 3000 OAuth."""

from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Response from Tone 3000 token exchange/refresh."""

    access_token: str
    refresh_token: str
    expires_in: int = Field(description="Token lifetime in seconds")


class Tone3000User(BaseModel):
    """User profile from Tone 3000 API."""

    id: int
    username: str
    avatar_url: str | None = None
    tones_count: int = 0


class UserResponse(BaseModel):
    """User response for API endpoints."""

    id: str
    tone3000_id: int
    username: str
    avatar_url: str | None
    created_at: datetime


class AuthStatus(BaseModel):
    """Authentication status response."""

    authenticated: bool
    user: UserResponse | None = None
