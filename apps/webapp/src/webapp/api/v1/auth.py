"""Authentication API endpoints.

Provides OAuth login flow endpoints:
- GET /api/v1/auth/login - Redirects to OAuth provider
- GET /api/v1/auth/callback - Handles OAuth callback
- GET /api/v1/auth/me - Returns current user info
- GET /api/v1/auth/logout - Clears session
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.auth.oauth import OAuthHandler
from webapp.auth.providers.t3k import T3KProvider
from webapp.services.identity_service import IdentityService

# Module-level session override for testing
# Tests can set this to provide a session without using dependency_overrides
_session_override: AsyncSession | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Set session override for testing.

    This allows tests to inject a database session without using FastAPI's
    dependency_overrides mechanism.

    Args:
        session: Database session to use, or None to clear override
    """
    global _session_override
    _session_override = session


async def get_db_session() -> AsyncSession:  # pragma: no cover
    """Get database session dependency.

    This should be overridden by the application or tests using
    app.dependency_overrides[get_db_session] = your_session_provider

    Alternatively, tests can use set_session_override() to inject a session.
    """
    if _session_override is not None:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/login")
async def login(
    request: Request,
    provider: str = Query(..., description="OAuth provider name (e.g., 't3k')"),
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Initiate OAuth login flow.

    Redirects to OAuth provider's authorization page.
    Stores OAuth state in session for CSRF validation.

    Args:
        request: FastAPI request object (for session access)
        provider: OAuth provider name (t3k, google, etc.)
        db_session: Database session

    Returns:
        307 redirect to OAuth authorization URL

    Raises:
        HTTPException: 400 if provider is invalid or disabled
    """
    try:
        oauth_handler = OAuthHandler(db_session)

        # Build redirect_uri from PUBLIC_URL (Traefik URL, not internal container URL)
        public_url = os.getenv("PUBLIC_URL", "http://localhost:9000")
        redirect_uri = f"{public_url}/api/v1/auth/callback"

        auth_url, state = await oauth_handler.generate_authorization_url(
            provider_name=provider,
            redirect_uri=redirect_uri,
            scope=None,
        )

        # Store state in session for CSRF validation on callback
        request.session["oauth_state"] = state
        request.session["oauth_provider"] = provider

        return RedirectResponse(url=auth_url, status_code=307)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def callback(
    request: Request,
    provider: str = Query(..., description="OAuth provider name"),
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Handle OAuth callback.

    Exchanges authorization code for tokens, retrieves user info,
    and creates or updates user account. Stores user_id in session.

    Args:
        request: FastAPI request object (for session access)
        provider: OAuth provider name
        code: Authorization code from OAuth provider
        state: State parameter for CSRF validation
        db_session: Database session

    Returns:
        302 redirect to library page

    Raises:
        HTTPException: 400/401 if callback validation fails
    """
    try:
        # Validate CSRF state from session
        expected_state = request.session.pop("oauth_state", None)
        if not expected_state or expected_state != state:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")

        oauth_handler = OAuthHandler(db_session)

        public_url = os.getenv("PUBLIC_URL", "http://localhost:9000")
        redirect_uri = f"{public_url}/api/v1/auth/callback"

        # Exchange code for tokens
        tokens = await oauth_handler.handle_callback(
            provider_name=provider,
            code=code,
            state=state,
            expected_state=expected_state,
            redirect_uri=redirect_uri,
        )

        # Get user info from provider
        if provider == "t3k":
            t3k_provider = T3KProvider()
            user_info = await t3k_provider.get_user_info(tokens["access_token"])
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Create or update user via IdentityService
        identity_service = IdentityService(db_session)
        user = await identity_service.get_or_create_user(
            provider_name=provider,
            external_id=user_info["id"],
            username=user_info["username"],
            email=user_info.get("email"),
            avatar_url=user_info.get("avatar_url"),
        )

        # Store user_id in session cookie
        request.session["user_id"] = str(user.id)

        return RedirectResponse(url="/library/my-gear", status_code=302)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback failed: {e!s}")


@router.get("/me")
async def get_current_user_info(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get current authenticated user from session.

    Args:
        request: FastAPI request object (for session access)
        db_session: Database session

    Returns:
        User profile data

    Raises:
        HTTPException: 401 if not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from uuid import UUID

    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        # Session has stale user_id — clear it
        request.session.clear()
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "avatar_url": user.avatar_url,
    }


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear session and redirect to home.

    Args:
        request: FastAPI request object (for session access)

    Returns:
        302 redirect to home page
    """
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)
