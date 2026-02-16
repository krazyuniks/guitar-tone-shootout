"""Scheduled T3K token refresh.

Runs every 5 minutes. Checks auth file expiry, refreshes proactively.
Conservative: no retry loops, no API calls when auth is unhealthy.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from core.domain.auth_gate import check_auth_status
from core.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)

# Refresh when token expires within this window
_REFRESH_WINDOW_SECONDS = 600  # 10 minutes

# Fallback refresh interval when no expires_at in auth file
_FALLBACK_REFRESH_SECONDS = 1800  # 30 minutes


def _update_auth_status(auth_file_path: str, status: SourceAuthStatus) -> None:
    """Update auth_status field in auth file. Best-effort."""
    path = Path(auth_file_path)
    try:
        with open(path) as f:
            data = json.load(f)
        data["auth_status"] = status.value
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except (json.JSONDecodeError, OSError):
        pass


async def refresh_t3k_token(
    auth_file_path: str | None = None,
    encryption_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Check token expiry and refresh if needed.

    Args:
        auth_file_path: Override for testing (default: GTS_AUTH_FILE env)
        encryption_key: Override for testing (default: OAUTH_ENCRYPTION_KEY env)
        base_url: Override for testing (default: T3K_API_URL env)
    """
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

    # Check auth gate
    status = check_auth_status(auth_file_path)
    if status == SourceAuthStatus.LOGIN_REQUIRED:
        logger.debug("Auth login_required — skipping refresh (run `just t3k-login`)")
        return

    # Read expiry info
    try:
        with open(path) as f:
            data = json.load(f)
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
            # Token is fine — ensure status is VALID
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
        # No expires_at — use saved_at as fallback
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

    # Set expiring_soon before attempting refresh
    _update_auth_status(auth_file_path, SourceAuthStatus.EXPIRING_SOON)

    # Attempt refresh via T3KTokenManager
    from source_t3k.adapters.inbound.exceptions import T3KAPIError
    from source_t3k.adapters.inbound.token_manager import T3KTokenManager

    token_manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    try:
        await token_manager.get_access_token()
        _update_auth_status(auth_file_path, SourceAuthStatus.VALID)
        logger.info("T3K token refreshed successfully")
    except T3KAPIError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "re-authenticate" in error_msg.lower():
            _update_auth_status(auth_file_path, SourceAuthStatus.LOGIN_REQUIRED)
            logger.error("T3K refresh token expired — run `just t3k-login`")
        else:
            _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
            logger.warning("T3K token refresh failed: %s", error_msg)
    except Exception:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.exception("Unexpected error during T3K token refresh")
    finally:
        await token_manager.close()


class _Schedule:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds


refresh_t3k_token.labels = {"schedule": [_Schedule(300)]}  # type: ignore[attr-defined]
