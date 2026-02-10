"""Authentication API endpoints.

Provides T3K login, callback, logout, session persistence, and status.
Uses JWT httponly cookies for stateless auth.
"""

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.auth.dependencies import (
    CurrentUser,
    CurrentUserOptional,
    get_db_session,
)
from webapp.auth.encryption import TokenEncryptor
from webapp.auth.persistence import AuthFilePersistence
from webapp.auth.providers.t3k import T3KProvider
from webapp.auth.token import JWT_COOKIE_NAME, JWT_EXPIRY_DAYS, create_access_token
from webapp.services.identity_service import IdentityService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Cookie settings
_COOKIE_MAX_AGE = 86400 * JWT_EXPIRY_DAYS  # 7 days in seconds


def _is_production() -> bool:
    return os.getenv("ENV") == "production"


def _get_auth_file() -> AuthFilePersistence:
    path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    return AuthFilePersistence(auth_file_path=path)


def _set_jwt_cookie(response: RedirectResponse | JSONResponse, token: str) -> None:
    """Set JWT token as httponly cookie on response."""
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_is_production(),
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


def _clear_jwt_cookie(response: RedirectResponse | JSONResponse) -> None:
    """Clear JWT cookie from response."""
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_is_production(),
        samesite="lax",
    )


def _get_next_url(request: Request) -> str | None:
    """Read ?next= parameter from request or from temp cookie."""
    next_url = request.query_params.get("next")
    if next_url and next_url.startswith("/"):
        return next_url
    # Check temp cookie set during login redirect
    next_url = request.cookies.get("gts_next")
    if next_url and next_url.startswith("/"):
        return next_url
    return None


# --- Login endpoints ---


@router.get("/login/t3k")
async def login_t3k(request: Request) -> RedirectResponse:
    """Redirect to T3K login page.

    Sets a temp cookie with ?next= URL so we can redirect after callback.
    """
    public_url = os.getenv("PUBLIC_URL", "http://localhost:9000")
    callback_url = f"{public_url}/api/v1/auth/callback"

    provider = T3KProvider()
    login_url = provider.build_login_url(callback_url)

    response = RedirectResponse(url=login_url, status_code=307)

    # Persist ?next= in a temp cookie for the callback
    next_url = request.query_params.get("next")
    if next_url and next_url.startswith("/"):
        response.set_cookie(
            key="gts_next",
            value=next_url,
            httponly=True,
            max_age=600,  # 10 minutes
            path="/",
            samesite="lax",
        )

    return response


@router.get("/login/{provider}")
async def login_provider(provider: str) -> RedirectResponse:
    """Redirect to provider login (returns 404 for unimplemented providers)."""
    raise HTTPException(
        status_code=404,
        detail=f"Provider '{provider}' is not available yet",
    )


# --- Callback ---


@router.get("/callback")
async def callback(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    api_key: str | None = Query(None),
) -> RedirectResponse:
    """Handle T3K callback with api_key parameter.

    Flow:
    1. Exchange api_key for access/refresh tokens
    2. Fetch user profile from T3K
    3. Create or update User + UserIdentity
    4. Issue JWT cookie
    5. Save tokens to auth file
    6. Redirect to ?next= URL or /library/my-gear
    """
    if not api_key:
        return RedirectResponse(url="/login?error=missing_api_key", status_code=302)

    provider = T3KProvider()

    try:
        # Exchange api_key for tokens
        token_data = await provider.exchange_api_key(api_key)
        access_token = token_data.get("access_token") or token_data.get("token")
        if not access_token:
            logger.error("T3K token exchange returned no access_token")
            return RedirectResponse(url="/login?error=token_exchange_failed", status_code=302)

        # Fetch user profile
        user_info = await provider.get_user_info(access_token)

        # Create or update user
        identity_service = IdentityService(db)
        user = await identity_service.get_or_create_user(
            provider_name="t3k",
            external_id=str(user_info.get("id", "")),
            username=user_info.get("username", ""),
            email=user_info.get("email"),
            avatar_url=user_info.get("avatar_url"),
        )

        # Create JWT
        jwt_token = create_access_token(user.id)

        # Determine redirect target
        next_url = _get_next_url(request) or "/library/my-gear"
        response = RedirectResponse(url=next_url, status_code=302)
        _set_jwt_cookie(response, jwt_token)

        # Clear temp next cookie
        response.delete_cookie(key="gts_next", path="/")

        # Save tokens to auth file
        try:
            encryptor = TokenEncryptor()
            auth_data = {
                "user_id": str(user.id),
                "username": user.username,
                "access_token": encryptor.encrypt(access_token),
                "expires_at": token_data.get("expires_at"),
                "provider": "t3k",
                "saved_at": datetime.now(UTC).isoformat(),
            }
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                auth_data["refresh_token"] = encryptor.encrypt(refresh_token)

            auth_file = _get_auth_file()
            auth_file.save(auth_data)
        except Exception:
            logger.warning("Failed to save auth file", exc_info=True)

        return response

    except Exception:
        logger.exception("T3K callback failed")
        return RedirectResponse(url="/login?error=callback_failed", status_code=302)


# --- User info ---


@router.get("/me")
async def get_me(current_user: CurrentUserOptional) -> dict:
    """Return current user info, or 401 if not authenticated."""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
    }


# --- Logout ---


@router.post("/logout")
async def logout_post(request: Request) -> JSONResponse:
    """Clear JWT cookie (for HTMX nav POST)."""
    response = JSONResponse(content={"status": "logged_out"})
    _clear_jwt_cookie(response)

    # Delete auth file
    try:
        auth_file = _get_auth_file()
        auth_file.delete()
    except Exception:
        logger.warning("Failed to delete auth file", exc_info=True)

    # Set HX-Redirect for HTMX
    response.headers["HX-Redirect"] = "/"
    return response


@router.get("/logout")
async def logout_get(request: Request) -> RedirectResponse:
    """Clear JWT cookie and redirect to home (browser-friendly)."""
    response = RedirectResponse(url="/", status_code=302)
    _clear_jwt_cookie(response)

    try:
        auth_file = _get_auth_file()
        auth_file.delete()
    except Exception:
        logger.warning("Failed to delete auth file", exc_info=True)

    return response


# --- Auth status ---


@router.get("/status")
async def auth_status() -> dict:
    """Return auth file validity and expiration. No auth required."""
    auth_file = _get_auth_file()
    data = auth_file.load()

    if data is None:
        return {"status": "no_auth_file", "valid": False}

    expires_at = data.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            now = datetime.now(UTC)
            if exp.tzinfo is None:
                # Assume UTC if no timezone
                exp = exp.replace(tzinfo=UTC)
            is_valid = exp > now
            return {
                "status": "valid" if is_valid else "expired",
                "valid": is_valid,
                "username": data.get("username"),
                "expires_at": expires_at,
                "provider": data.get("provider"),
            }
        except (ValueError, TypeError):
            pass

    # No expiration set — treat as valid if user_id present
    has_user = bool(data.get("user_id"))
    return {
        "status": "valid" if has_user else "unknown",
        "valid": has_user,
        "username": data.get("username"),
        "provider": data.get("provider"),
    }


# --- Session save/restore ---


@router.post("/save-session")
async def save_session(current_user: CurrentUser) -> dict:
    """Save current T3K tokens to auth file. Requires auth."""
    # Auth file is already saved during callback. This endpoint allows
    # explicit re-save if needed.
    auth_file = _get_auth_file()
    data = auth_file.load()
    if data is None:
        raise HTTPException(status_code=404, detail="No session data to save")

    # Update saved_at timestamp
    data["saved_at"] = datetime.now(UTC).isoformat()
    auth_file.save(data)

    return {"status": "saved", "username": current_user.username}


@router.post("/restore-session")
async def restore_session_post(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Restore session from auth file, set JWT cookie."""
    return await _restore_session(request, db, redirect=False)


@router.get("/restore-session", response_model=None)
async def restore_session_get(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Restore session from auth file, redirect to library."""
    return await _restore_session(request, db, redirect=True)


async def _restore_session(
    request: Request,
    db: AsyncSession,
    redirect: bool,
) -> RedirectResponse | JSONResponse:
    """Common restore logic."""
    auth_file = _get_auth_file()
    data = auth_file.load()

    if data is None:
        if redirect:
            return RedirectResponse(url="/login?error=no_session", status_code=302)
        raise HTTPException(status_code=404, detail="No auth file found")

    user_id = data.get("user_id")
    if not user_id:
        if redirect:
            return RedirectResponse(url="/login?error=invalid_session", status_code=302)
        raise HTTPException(status_code=400, detail="Invalid auth file")

    # Verify user exists
    from uuid import UUID

    from sqlalchemy import select

    from webapp.adapters.persistence.models.user import User

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        if redirect:
            return RedirectResponse(url="/login?error=user_not_found", status_code=302)
        raise HTTPException(status_code=404, detail="User not found")

    # Issue new JWT
    jwt_token = create_access_token(user.id)

    if redirect:
        next_url = _get_next_url(request) or "/library/my-gear"
        response = RedirectResponse(url=next_url, status_code=302)
    else:
        response = JSONResponse(
            content={
                "status": "restored",
                "username": user.username,
            }
        )

    _set_jwt_cookie(response, jwt_token)
    return response


# --- Provider unlinking (future) ---


@router.delete("/unlink/{provider}")
async def unlink_provider(provider: str, current_user: CurrentUser) -> dict:
    """Unlink a provider from user account. Future endpoint."""
    raise HTTPException(
        status_code=501,
        detail=f"Unlinking '{provider}' is not yet implemented",
    )
