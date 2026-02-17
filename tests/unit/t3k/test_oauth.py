"""Unit tests for T3K token manager.

Tests verify file-based token loading, Fernet decryption, expiry checks,
and token refresh via HTTP. External T3K API calls use httpx MockTransport.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient, MockTransport, Request, Response

from source_t3k.adapters.inbound.token_manager import T3KTokenManager


def _make_auth_file(
    tmp_path: Path,
    fernet: Fernet,
    access_token: str = "test-access-token",
    refresh_token: str = "test-refresh-token",
    expires_at: datetime | None = None,
) -> str:
    """Create a .gts-auth.json file and return its path."""
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=1)

    data = {
        "access_token": fernet.encrypt(access_token.encode()).decode(),
        "refresh_token": fernet.encrypt(refresh_token.encode()).decode(),
        "expires_at": expires_at.isoformat(),
        "auth_status": "valid",
    }
    auth_file = tmp_path / ".gts-auth.json"
    auth_file.write_text(json.dumps(data))
    return str(auth_file)


@pytest.fixture
def encryption_key() -> str:
    """Generate a Fernet encryption key for testing."""
    return Fernet.generate_key().decode()


@pytest.fixture
def fernet(encryption_key: str) -> Fernet:
    return Fernet(encryption_key.encode())


def _make_manager(
    auth_file_path: str,
    encryption_key: str,
    handler=None,
    base_url: str = "https://oauth.tone3000.com",
) -> T3KTokenManager:
    """Create a T3KTokenManager with optional MockTransport handler."""
    manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    if handler is not None:
        manager._client = AsyncClient(transport=MockTransport(handler))
    return manager


class TestTokenLoading:
    """Test loading tokens from auth file."""

    async def test_loads_valid_token_from_file(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """get_access_token() returns decrypted access token from auth file."""
        auth_file = _make_auth_file(tmp_path, fernet, access_token="valid-access-token")
        manager = _make_manager(auth_file, encryption_key)

        token = await manager.get_access_token()
        assert token == "valid-access-token"

    async def test_raises_when_auth_file_missing(self, tmp_path: Path, encryption_key: str) -> None:
        """get_access_token() raises T3KAPIError when auth file does not exist."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        manager = _make_manager(str(tmp_path / "missing.json"), encryption_key)
        with pytest.raises(T3KAPIError, match="Auth file not found"):
            await manager.get_access_token()

    async def test_raises_when_no_access_token_in_file(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        """get_access_token() raises T3KAPIError when access_token field is missing."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        auth_file = tmp_path / ".gts-auth.json"
        auth_file.write_text(json.dumps({"auth_status": "valid"}))

        manager = _make_manager(str(auth_file), encryption_key)
        with pytest.raises(T3KAPIError, match="No access_token in auth file"):
            await manager.get_access_token()


class TestTokenCaching:
    """Test in-memory token caching."""

    async def test_returns_cached_token_on_second_call(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """Second call returns cached token without re-reading file."""
        auth_file = _make_auth_file(tmp_path, fernet, access_token="cached-token")
        manager = _make_manager(auth_file, encryption_key)

        token1 = await manager.get_access_token()
        # Delete auth file — second call should use cache
        Path(auth_file).unlink()

        token2 = await manager.get_access_token()
        assert token1 == token2 == "cached-token"


class TestTokenExpiry:
    """Test token expiry checks and automatic refresh."""

    async def test_expired_token_triggers_refresh(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """get_access_token() refreshes token when expired."""
        post_count = 0

        def handler(_request: Request) -> Response:
            nonlocal post_count
            post_count += 1
            return Response(
                200,
                json={
                    "access_token": "refreshed-access-token",
                    "refresh_token": "refreshed-refresh-token",
                    "expires_in": 3600,
                },
            )

        expired_at = datetime.now(UTC) - timedelta(minutes=5)
        auth_file = _make_auth_file(
            tmp_path, fernet, access_token="old-token", expires_at=expired_at
        )
        manager = _make_manager(auth_file, encryption_key, handler=handler)

        token = await manager.get_access_token()
        assert token == "refreshed-access-token"
        assert post_count == 1

    async def test_near_expiry_token_triggers_refresh(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """Token within 5-minute buffer triggers refresh preemptively."""
        post_count = 0

        def handler(_request: Request) -> Response:
            nonlocal post_count
            post_count += 1
            return Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )

        # Token expires in 3 minutes — within 5-minute buffer
        near_expiry = datetime.now(UTC) + timedelta(minutes=3)
        auth_file = _make_auth_file(
            tmp_path, fernet, access_token="old-token", expires_at=near_expiry
        )
        manager = _make_manager(auth_file, encryption_key, handler=handler)

        token = await manager.get_access_token()
        assert token == "new-access-token"
        assert post_count == 1


class TestTokenRefresh:
    """Test OAuth token refresh via HTTP."""

    async def test_refresh_calls_correct_endpoint(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """_refresh() calls T3K session refresh endpoint."""
        captured_requests: list[Request] = []

        def handler(request: Request) -> Response:
            captured_requests.append(request)
            return Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )

        expired_at = datetime.now(UTC) - timedelta(minutes=10)
        auth_file = _make_auth_file(tmp_path, fernet, expires_at=expired_at)
        manager = _make_manager(
            auth_file, encryption_key, handler=handler, base_url="https://oauth.tone3000.com"
        )

        await manager.get_access_token()

        assert len(captured_requests) == 1
        assert "/auth/session/refresh" in str(captured_requests[0].url)

    async def test_refresh_saves_new_tokens_to_auth_file(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """After refresh, new tokens are encrypted and saved to auth file."""

        def handler(_request: Request) -> Response:
            return Response(
                200,
                json={
                    "access_token": "saved-access-token",
                    "refresh_token": "saved-refresh-token",
                    "expires_in": 3600,
                },
            )

        expired_at = datetime.now(UTC) - timedelta(minutes=10)
        auth_file = _make_auth_file(tmp_path, fernet, expires_at=expired_at)
        manager = _make_manager(auth_file, encryption_key, handler=handler)

        await manager.get_access_token()

        # Verify new tokens were saved to auth file
        saved = json.loads(Path(auth_file).read_text())
        decrypted_access = fernet.decrypt(saved["access_token"].encode()).decode()
        assert decrypted_access == "saved-access-token"

    async def test_refresh_raises_on_401(
        self, tmp_path: Path, encryption_key: str, fernet: Fernet
    ) -> None:
        """_refresh() raises T3KAPIError when refresh endpoint returns 401."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        def handler(_request: Request) -> Response:
            return Response(401, json={"error": "unauthorized"})

        expired_at = datetime.now(UTC) - timedelta(minutes=10)
        auth_file = _make_auth_file(tmp_path, fernet, expires_at=expired_at)
        manager = _make_manager(auth_file, encryption_key, handler=handler)

        with pytest.raises(T3KAPIError, match="refresh token expired"):
            await manager.get_access_token()
