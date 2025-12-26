"""Security utilities for JWT token handling."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings


class TokenError(Exception):
    """Exception raised for token-related errors."""


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token for the user.

    Args:
        user_id: The user's UUID as a string
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    encoded: str = jwt.encode(
        payload, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded


def decode_access_token(token: str) -> str:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string

    Returns:
        The user_id from the token

    Raises:
        TokenError: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise TokenError("Token missing user ID")
        return user_id
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}") from e
