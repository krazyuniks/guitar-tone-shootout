"""Integration tests for T3K authentication flow (T15).

Tests end-to-end T3K authentication flow:
- Login URL generation for T3K api_key flow
- API key exchange with T3K
- User info retrieval from T3K API
- Custom API URL from environment variable
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


from typing import Any

import httpx
import pytest
from httpx import HTTPStatusError, Request, Response

from webapp.adapters.persistence.models.user import OAuthProvider


class FakeHttpxResponse:
    """Test double for httpx.Response that returns canned JSON."""

    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        pass


@pytest.fixture
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a T3K OAuth provider with real credentials format."""
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    provider = OAuthProvider(
        name=f"t3k_{suffix}",
        client_id="gts_client_id_123",
        client_secret="gts_client_secret_456",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestT3KAuthIntegration:
    """Integration tests for T3K auth flow."""

    def test_t3k_provider_builds_login_url(self, t3k_provider: OAuthProvider) -> None:
        """Test T3KProvider generates valid login URL with redirect."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()
        callback = "http://localhost:9000/auth/callback"

        url = t3k.build_login_url(callback)

        assert "tone3000.com" in url
        assert "/api/v1/auth" in url
        assert f"redirect_url={callback}" in url

    async def test_full_t3k_auth_flow_with_api_key(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test complete T3K auth flow: api_key exchange + user info retrieval."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        token_response = {
            "access_token": "t3k_access_abc123",
            "refresh_token": "t3k_refresh_def456",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        user_info_response = {
            "id": "t3k_user_789",
            "username": "tone_enthusiast",
            "email": "user@tone3000.com",
        }

        async def fake_post(self_client: Any, *args: Any, **kwargs: Any) -> FakeHttpxResponse:
            return FakeHttpxResponse(token_response)

        async def fake_get(self_client: Any, *args: Any, **kwargs: Any) -> FakeHttpxResponse:
            return FakeHttpxResponse(user_info_response)

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        # Exchange api_key for tokens
        tokens = await t3k.exchange_api_key("test_api_key")
        assert tokens["access_token"] == "t3k_access_abc123"
        assert tokens["refresh_token"] == "t3k_refresh_def456"

        # Fetch user info using access token
        user_info = await t3k.get_user_info(access_token=tokens["access_token"])

        assert user_info["id"] == "t3k_user_789"
        assert user_info["username"] == "tone_enthusiast"
        assert user_info["email"] == "user@tone3000.com"

    async def test_t3k_api_key_exchange_handles_failure(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test T3K api_key exchange handles HTTP errors."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        error_response = Response(
            status_code=401,
            json={"error": "invalid_api_key"},
        )
        error_request = Request("POST", f"{t3k.base_url}/api/v1/auth/session")

        async def fake_post(self_client: Any, *args: Any, **kwargs: Any) -> None:
            raise HTTPStatusError("Unauthorized", request=error_request, response=error_response)

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(HTTPStatusError):
            await t3k.exchange_api_key("invalid_key")

    async def test_t3k_user_info_handles_unauthorized(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test T3K provider handles 401 Unauthorized when fetching user info."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        error_response = Response(
            status_code=401,
            json={"error": "invalid_token"},
        )
        error_request = Request("GET", f"{t3k.base_url}/api/v1/user")

        async def fake_get(self_client: Any, *args: Any, **kwargs: Any) -> None:
            raise HTTPStatusError("Unauthorized", request=error_request, response=error_response)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        with pytest.raises(HTTPStatusError):
            await t3k.get_user_info(access_token="expired_token")

    def test_t3k_uses_custom_api_url_from_env(
        self, t3k_provider: OAuthProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test T3K provider uses custom API URL from environment."""
        from webapp.auth.providers.t3k import T3KProvider

        custom_api_url = "https://staging.tone3000.com"

        monkeypatch.setenv("T3K_API_URL", custom_api_url)
        t3k = T3KProvider()
        assert t3k.base_url == custom_api_url

        url = t3k.build_login_url("http://localhost/callback")
        assert custom_api_url in url

    async def test_t3k_provider_returns_complete_user_profile(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test T3K provider returns all user profile fields."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        user_info_data = {
            "id": "t3k_12345",
            "username": "guitar_wizard",
            "email": "wizard@tone3000.com",
            "avatar_url": "https://tone3000.com/avatars/wizard.jpg",
            "created_at": "2024-01-15T10:30:00Z",
        }

        async def fake_get(self_client: Any, *args: Any, **kwargs: Any) -> FakeHttpxResponse:
            return FakeHttpxResponse(user_info_data)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        user_info = await t3k.get_user_info(access_token="valid_token")

        assert user_info["id"] == "t3k_12345"
        assert user_info["username"] == "guitar_wizard"
        assert user_info["email"] == "wizard@tone3000.com"
        assert user_info["avatar_url"] == "https://tone3000.com/avatars/wizard.jpg"
