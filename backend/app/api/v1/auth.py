"""Authentication endpoints for Tone 3000 OAuth.

This module implements the OAuth flow with Tone 3000:
1. /login - Redirects user to Tone 3000 authentication
2. /callback - Handles the redirect with api_key, exchanges for tokens
3. /logout - Clears the session
4. /me - Returns current authenticated user
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUserOptional, DbSession
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import AuthStatus, TokenResponse, Tone3000User, UserResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

TONE3000_API = "https://www.tone3000.com/api/v1"


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect user to Tone 3000 authentication page.

    The user will authenticate on Tone 3000 and be redirected back
    to our callback endpoint with an api_key parameter.
    """
    callback_url = f"{settings.app_url}/api/v1/auth/callback"
    encoded_callback = quote(callback_url, safe="")
    redirect_url = f"{TONE3000_API}/auth?redirect_url={encoded_callback}"

    logger.info("Redirecting user to Tone 3000 auth")
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def callback(api_key: str, db: DbSession) -> RedirectResponse:
    """Handle OAuth callback from Tone 3000.

    Exchanges the api_key for access/refresh tokens, fetches user profile,
    creates/updates local user, and sets session cookie.

    Args:
        api_key: The API key from Tone 3000 redirect
        db: Database session

    Returns:
        Redirect to frontend with session cookie set
    """
    try:
        # Exchange api_key for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                f"{TONE3000_API}/auth/session",
                json={"api_key": api_key},
                timeout=10.0,
            )
            token_response.raise_for_status()
            tokens = TokenResponse(**token_response.json())

            # Fetch user profile
            profile_response = await client.get(
                f"{TONE3000_API}/user",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                timeout=10.0,
            )
            profile_response.raise_for_status()
            profile = Tone3000User(**profile_response.json())

    except httpx.HTTPStatusError as e:
        logger.error("Tone 3000 API error: %s", e.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to authenticate with Tone 3000",
        ) from e
    except httpx.RequestError as e:
        logger.error("Tone 3000 connection error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to Tone 3000",
        ) from e

    # Get or create local user
    user = await _get_or_create_user(db, profile, tokens)

    # Create session token
    session_token = create_access_token(str(user.id))

    # Redirect to frontend with cookie
    response = RedirectResponse(
        url=settings.frontend_url, status_code=status.HTTP_302_FOUND
    )
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=not settings.debug,  # Secure in production
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )

    logger.info("User %s logged in successfully", user.username)
    return response


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the session cookie to log out the user."""
    response.delete_cookie(key="session")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AuthStatus)
async def me(
    user: CurrentUserOptional,
) -> AuthStatus:
    """Get current authenticated user.

    Returns authentication status and user info if logged in.
    """
    if user is None:
        return AuthStatus(authenticated=False)

    return AuthStatus(
        authenticated=True,
        user=UserResponse(
            id=str(user.id),
            tone3000_id=user.tone3000_id,
            username=user.username,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
        ),
    )


async def _get_or_create_user(
    db: DbSession, profile: Tone3000User, tokens: TokenResponse
) -> User:
    """Get existing user or create new one from Tone 3000 profile.

    Args:
        db: Database session
        profile: User profile from Tone 3000
        tokens: OAuth tokens from Tone 3000

    Returns:
        The local user record
    """
    # Look for existing user by Tone 3000 ID
    stmt = select(User).where(User.tone3000_id == profile.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    token_expires = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)

    if user is None:
        # Create new user
        user = User(
            tone3000_id=profile.id,
            username=profile.username,
            avatar_url=profile.avatar_url,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_expires_at=token_expires,
        )
        db.add(user)
        logger.info("Created new user: %s", profile.username)
    else:
        # Update existing user
        user.username = profile.username
        user.avatar_url = profile.avatar_url
        user.access_token = tokens.access_token
        user.refresh_token = tokens.refresh_token
        user.token_expires_at = token_expires
        logger.info("Updated existing user: %s", profile.username)

    await db.commit()
    await db.refresh(user)
    return user
