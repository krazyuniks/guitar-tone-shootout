"""T3K API token manager.

Loads encrypted OAuth tokens from .gts-auth.json, decrypts them with
Fernet, caches in memory, and refreshes via POST /api/v1/auth/session/refresh
when near expiry.
"""

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from httpx import AsyncClient

from core.domain.value_objects.source_auth_status import SourceAuthStatus
from source_t3k.adapters.inbound.exceptions import T3KAPIError
from source_t3k.adapters.inbound.vercel_solver import is_vercel_challenge, solve_challenge

logger = logging.getLogger(__name__)

# Refresh token when within this many seconds of expiry.
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


class T3KTokenManager:
    """Manages OAuth token lifecycle for T3K API authentication.

    Loads encrypted tokens from .gts-auth.json, decrypts with Fernet,
    and refreshes via the T3K refresh endpoint when expired.
    """

    def __init__(self, auth_file_path: str, base_url: str, encryption_key: str) -> None:
        self._auth_file_path = auth_file_path
        self._base_url = base_url.rstrip("/")
        self._fernet = Fernet(
            encryption_key.encode("utf-8") if isinstance(encryption_key, str) else encryption_key
        )
        from source_t3k.adapters.inbound.vercel_solver import load_cookies

        vercel_cookies = load_cookies()
        self._client = AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Content-Type": "application/json",
            },
            cookies=vercel_cookies or None,
        )
        self._lock = asyncio.Lock()

        # Cached token state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0  # unix timestamp

    async def get_access_token(self) -> str:
        """Return a valid access token, loading or refreshing as needed."""
        if self._access_token and time.time() < self._expires_at - _REFRESH_BUFFER_SECONDS:
            return self._access_token

        async with self._lock:
            # Double-check after acquiring lock
            if self._access_token and time.time() < self._expires_at - _REFRESH_BUFFER_SECONDS:
                return self._access_token

            if self._access_token is None:
                self._load_from_auth_file()

            if time.time() >= self._expires_at - _REFRESH_BUFFER_SECONDS:
                await self._refresh()

            assert self._access_token is not None
            return self._access_token

    def _load_from_auth_file(self) -> None:
        """Load and decrypt tokens from .gts-auth.json."""
        path = Path(self._auth_file_path)
        if not path.exists():
            raise T3KAPIError(
                f"Auth file not found at {self._auth_file_path} — authenticate via browser"
            )

        with open(path) as f:
            data = json.load(f)

        encrypted_access = data.get("access_token")
        if not encrypted_access:
            raise T3KAPIError("No access_token in auth file — authenticate via browser")

        try:
            self._access_token = self._fernet.decrypt(encrypted_access.encode("utf-8")).decode(
                "utf-8"
            )
        except InvalidToken as e:
            raise T3KAPIError("Token decryption failed — re-authenticate via browser") from e

        encrypted_refresh = data.get("refresh_token")
        if encrypted_refresh:
            try:
                self._refresh_token = self._fernet.decrypt(
                    encrypted_refresh.encode("utf-8")
                ).decode("utf-8")
            except InvalidToken as e:
                raise T3KAPIError(
                    "Refresh token decryption failed — re-authenticate via browser"
                ) from e

        expires_at_str = data.get("expires_at")
        if expires_at_str:
            expires_dt = datetime.fromisoformat(expires_at_str)
            self._expires_at = expires_dt.timestamp()
        else:
            # No expiry info — assume valid for 1 hour from now
            self._expires_at = time.time() + 3600

        logger.info("Loaded T3K tokens from auth file")

    async def _refresh(self) -> None:
        """Refresh the access token via POST /api/v1/auth/session/refresh."""
        if not self._refresh_token:
            raise T3KAPIError("No refresh token — re-authenticate via browser")

        for attempt in range(3):
            response = await self._client.post(
                f"{self._base_url}/api/v1/auth/session/refresh",
                json={
                    "refresh_token": self._refresh_token,
                    "access_token": self._access_token or "",
                },
            )

            if response.status_code == 401:
                self._update_auth_status_field(SourceAuthStatus.LOGIN_REQUIRED)
                raise T3KAPIError("T3K refresh token expired — re-authenticate via browser")

            if is_vercel_challenge(response.status_code, response.text):
                logger.warning("Vercel challenge on refresh (attempt %d/3)", attempt + 1)
                if solve_challenge(self._base_url):
                    continue
                raise T3KAPIError("Vercel challenge could not be solved during token refresh")

            response.raise_for_status()

            data = response.json()
            new_access = data["access_token"]
            new_refresh = data.get("refresh_token", self._refresh_token)
            expires_in = data.get("expires_in", 3600)

            # Update in-memory cache
            self._access_token = new_access
            self._refresh_token = new_refresh
            self._expires_at = time.time() + expires_in

            # Encrypt and save to auth file
            self._save_to_auth_file(new_access, new_refresh, expires_in)

            logger.info("T3K token refreshed, expires in %ds", expires_in)
            return

        raise T3KAPIError("Token refresh failed after Vercel challenge retries")

    def _save_to_auth_file(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """Encrypt tokens and update .gts-auth.json."""
        path = Path(self._auth_file_path)

        # Load existing data to preserve user_id, username, etc.
        existing: dict = {}
        if path.exists():
            with open(path) as f:
                existing = json.load(f)

        expires_at = datetime.now(UTC).timestamp() + expires_in
        expires_at_iso = datetime.fromtimestamp(expires_at, tz=UTC).isoformat()

        existing["access_token"] = self._fernet.encrypt(access_token.encode("utf-8")).decode(
            "utf-8"
        )
        existing["refresh_token"] = self._fernet.encrypt(refresh_token.encode("utf-8")).decode(
            "utf-8"
        )
        existing["expires_at"] = expires_at_iso
        existing["auth_status"] = SourceAuthStatus.VALID.value
        existing["saved_at"] = datetime.now(UTC).isoformat()

        with open(path, "w") as f:
            json.dump(existing, f, indent=2)

        os.chmod(path, 0o600)

    def _update_auth_status_field(self, status: SourceAuthStatus) -> None:
        """Update only the auth_status field in the auth file."""
        path = Path(self._auth_file_path)
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            data["auth_status"] = status.value
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except (json.JSONDecodeError, OSError):
            pass  # Best-effort — don't crash on status update failure

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
