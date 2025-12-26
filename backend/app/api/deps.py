"""Dependency injection for API endpoints.

Common dependencies used across API endpoints are defined here.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.database import get_db
from app.core.security import TokenError, decode_access_token
from app.models.user import User


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        The application settings instance.
    """
    return settings


_get_db = Depends(get_db)
_session_cookie = Cookie(default=None)


async def get_current_user(
    session: str | None = _session_cookie,
    db: AsyncSession = _get_db,
) -> User:
    """Get the current authenticated user from session cookie.

    Args:
        session: Session token from cookie
        db: Database session

    Returns:
        The authenticated user

    Raises:
        HTTPException: If not authenticated or user not found
    """
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        user_id = decode_access_token(session)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_current_user_optional(
    session: str | None = _session_cookie,
    db: AsyncSession = _get_db,
) -> User | None:
    """Get the current user if authenticated, None otherwise.

    Args:
        session: Session token from cookie
        db: Database session

    Returns:
        The authenticated user or None if not logged in
    """
    if session is None:
        return None

    try:
        user_id = decode_access_token(session)
    except TokenError:
        return None

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
