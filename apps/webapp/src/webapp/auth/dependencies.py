"""Centralised auth dependencies for FastAPI routes.

Provides JWT cookie-based authentication via FastAPI Depends().
All route modules import from here instead of duplicating auth logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.auth.token import JWT_COOKIE_NAME, decode_access_token

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Module-level overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Set session override for testing."""
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Set user override for testing."""
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency.

    Async generator so FastAPI properly closes the session after each request.
    Checks for test override first, then falls back to global factory.
    """
    if _session_override is not None:
        yield _session_override
        return
    from webapp.dependencies import get_db

    async for session in get_db():
        yield session


async def _get_user_from_cookie(
    request: Request,
    db: AsyncSession,
) -> User | None:
    """Read JWT from cookie, decode, and look up User.

    Returns None if no cookie, expired, or user not found.
    """
    token = request.cookies.get(JWT_COOKIE_NAME)
    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        return None

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Get current user if authenticated, None otherwise.

    For public pages that optionally show user-specific content.
    """
    if _user_override is not None:
        return _user_override
    return await _get_user_from_cookie(request, db)


async def get_current_user_required(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Require authenticated user — raises 401 if not authenticated.

    For protected pages and API endpoints.
    """
    if _user_override is not None:
        return _user_override
    user = await _get_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


# Type aliases for use in route signatures
CurrentUser = Annotated[User, Depends(get_current_user_required)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
