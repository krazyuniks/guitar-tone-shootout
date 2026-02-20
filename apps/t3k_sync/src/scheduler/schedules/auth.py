"""Scheduled T3K token refresh."""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from core.domain.auth_gate import check_auth_status
from core.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)

_REFRESH_WINDOW_SECONDS = 600
_FALLBACK_REFRESH_SECONDS = 1800


def _update_auth_status(auth_file_path: str, status: SourceAuthStatus) -> None:
    """Update auth_status field in auth file. Best-effort."""
    path = Path(auth_file_path)
    try:
        with open(path) as file_handle:
            data = json.load(file_handle)
        data["auth_status"] = status.value
        with open(path, "w") as file_handle:
            json.dump(data, file_handle, indent=2)
    except (json.JSONDecodeError, OSError):
        pass


async def refresh_t3k_token(
    auth_file_path: str | None = None,
    encryption_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Check token expiry and refresh if needed."""
    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    if encryption_key is None:
        encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if base_url is None:
        base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")

    path = Path(auth_file_path)
    if not path.exists():
        logger.debug("Auth file not found: %s", auth_file_path)
        return

    status = check_auth_status(auth_file_path)
    if status == SourceAuthStatus.LOGIN_REQUIRED:
        logger.debug("Auth login_required — skipping refresh (run `just t3k-login`)")
        return

    try:
        with open(path) as file_handle:
            data = json.load(file_handle)
    except (json.JSONDecodeError, OSError):
        return

    expires_at_str = data.get("expires_at")
    saved_at_str = data.get("saved_at")
    now = datetime.now(UTC)

    needs_refresh = False

    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        seconds_until_expiry = (expires_at - now).total_seconds()

        if seconds_until_expiry > _REFRESH_WINDOW_SECONDS:
            if status != SourceAuthStatus.VALID:
                _update_auth_status(auth_file_path, SourceAuthStatus.VALID)
            return

        logger.info(
            "Token expires in %.0f seconds (within %d-second window)",
            seconds_until_expiry,
            _REFRESH_WINDOW_SECONDS,
        )
        needs_refresh = True
    elif saved_at_str:
        saved_at = datetime.fromisoformat(saved_at_str)
        if saved_at.tzinfo is None:
            saved_at = saved_at.replace(tzinfo=UTC)
        age = (now - saved_at).total_seconds()
        if age < _FALLBACK_REFRESH_SECONDS:
            return
        logger.info("No expires_at, last saved %.0f seconds ago — refreshing", age)
        needs_refresh = True
    else:
        logger.warning("Auth file has no expires_at or saved_at — skipping")
        return

    if not needs_refresh:
        return

    if not encryption_key:
        logger.error("OAUTH_ENCRYPTION_KEY not set — cannot refresh")
        return

    _update_auth_status(auth_file_path, SourceAuthStatus.EXPIRING_SOON)

    worker_url = os.getenv("WORKER_ADMIN_URL", "http://worker:8001")
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{worker_url}/api/admin/auth/refresh-t3k",
                json={
                    "auth_file_path": auth_file_path,
                    "base_url": base_url,
                    "encryption_key": encryption_key,
                },
            )
            response.raise_for_status()
            result = response.json()
            new_status_str = result.get("auth_status", "refresh_failed")
            try:
                new_status = SourceAuthStatus(new_status_str)
            except ValueError:
                new_status = SourceAuthStatus.REFRESH_FAILED
            _update_auth_status(auth_file_path, new_status)
            if new_status == SourceAuthStatus.VALID:
                logger.info("T3K token refreshed successfully")
            elif new_status == SourceAuthStatus.LOGIN_REQUIRED:
                logger.error("T3K refresh token expired — run `just t3k-login`")
            else:
                logger.warning("T3K token refresh failed — status: %s", new_status_str)
    except httpx.HTTPStatusError as error:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.error("Worker returned error during T3K token refresh: %s", error)
    except httpx.RequestError as error:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.error("Worker unreachable during T3K token refresh: %s", error)
    except Exception:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.exception("Unexpected error during T3K token refresh")


refresh_t3k_token.labels = {"schedule": [{"interval": 300}]}  # type: ignore[attr-defined]
