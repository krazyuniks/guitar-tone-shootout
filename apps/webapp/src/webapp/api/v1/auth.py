"""Authentication API endpoints.

Provides OAuth login flow endpoints:
- GET /api/v1/auth/login - Redirects to OAuth provider
- GET /api/v1/auth/callback - Handles OAuth callback
- GET /api/v1/auth/me - Returns current user info
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
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
    provider: str = Query(..., description="OAuth provider name (e.g., 't3k')"),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Initiate OAuth login flow.

    Redirects to OAuth provider's authorization page.

    Args:
        provider: OAuth provider name (t3k, google, etc.)
        db_session: Database session

    Returns:
        307 redirect to OAuth authorization URL

    Raises:
        HTTPException: 400 if provider is invalid or disabled
    """
    try:
        oauth_handler = OAuthHandler(db_session)

        # Generate authorization URL
        # In production, redirect_uri would be built from request.base_url
        redirect_uri = "http://localhost:8000/api/v1/auth/callback"

        auth_url, state = await oauth_handler.generate_authorization_url(
            provider_name=provider,
            redirect_uri=redirect_uri,
            scope=None,
        )

        # TODO: Store state in session for CSRF validation

        # Redirect to OAuth provider
        return Response(
            status_code=307,
            headers={"location": auth_url},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def callback(
    provider: str = Query(..., description="OAuth provider name"),
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Handle OAuth callback.

    Exchanges authorization code for tokens, retrieves user info,
    and creates or updates user account.

    Args:
        provider: OAuth provider name
        code: Authorization code from OAuth provider
        state: State parameter for CSRF validation
        db_session: Database session

    Returns:
        200 response with user data or 302 redirect to app

    Raises:
        HTTPException: 400/401 if callback validation fails
    """
    try:
        oauth_handler = OAuthHandler(db_session)

        # TODO: Retrieve expected_state from session
        expected_state = state  # Placeholder - in production, read from session

        redirect_uri = "http://localhost:8000/api/v1/auth/callback"

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

        # TODO: Create session or return JWT token
        # For now, return user data
        return Response(
            status_code=200,
            content=f'{{"id": "{user.id}", "username": "{user.username}"}}',
            media_type="application/json",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback failed: {e!s}")


@router.get("/me")
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get current authenticated user.

    Requires Bearer token in Authorization header.

    Args:
        authorization: Authorization header with Bearer token
        db_session: Database session

    Returns:
        User profile data

    Raises:
        HTTPException: 401 if not authenticated or token invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization[7:]  # Remove "Bearer " prefix

    # TODO: Validate token and get user_id
    # For now, this is a placeholder that will be mocked in tests
    try:
        # Import here to avoid circular dependency
        from webapp.auth.token import validate_token

        user_id = validate_token(token)

        # Fetch user from database
        from sqlalchemy import select

        result = await db_session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "avatar_url": user.avatar_url,
        }

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
