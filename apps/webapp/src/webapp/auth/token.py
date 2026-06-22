"""JWT token utilities for session management.

Creates and validates JWT tokens used in httponly cookies for
stateless authentication.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from webapp.config.secrets import get_app_secret_key

JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "gts_session"
JWT_EXPIRY_DAYS = 7


def _get_secret_key() -> str:
    return get_app_secret_key()


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a JWT access token for the given user.

    Args:
        user_id: User UUID to encode in the token

    Returns:
        Encoded JWT string
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dictionary

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
    """
    return jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])


def get_user_id_from_token(token: str) -> uuid.UUID:
    """Extract user ID from a JWT token.

    Args:
        token: JWT token string

    Returns:
        User UUID from the 'sub' claim

    Raises:
        jwt.InvalidTokenError: If token is invalid
        ValueError: If sub claim is not a valid UUID
    """
    payload = decode_access_token(token)
    return uuid.UUID(payload["sub"])
