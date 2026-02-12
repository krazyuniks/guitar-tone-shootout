"""Integration tests for T3K authentication flow (T15).

Tests end-to-end T3K authentication flow:
- Login URL generation for T3K api_key flow
- API key exchange with T3K
- User info retrieval from T3K API
- Custom API URL from environment variable
"""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from httpx import HTTPStatusError, Request, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Real database with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    async_session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a T3K OAuth provider with real credentials format."""
    provider = OAuthProvider(
        name="t3k",
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
        callback = "http://localhost:9000/api/v1/auth/callback"

        url = t3k.build_login_url(callback)

        assert "tone3000.com" in url
        assert "/api/v1/auth" in url
        assert f"redirect_url={callback}" in url

    async def test_full_t3k_auth_flow_with_api_key(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test complete T3K auth flow: api_key exchange + user info retrieval."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        # Step 1: Mock api_key exchange
        mock_token_response = {
            "access_token": "t3k_access_abc123",
            "refresh_token": "t3k_refresh_def456",
            "expires_at": "2099-01-01T00:00:00Z",
        }

        # Step 2: Mock user info
        mock_user_info = {
            "id": "t3k_user_789",
            "username": "tone_enthusiast",
            "email": "user@tone3000.com",
        }

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("httpx.AsyncClient.get") as mock_get,
        ):
            # Mock api_key exchange response
            mock_token_resp = MagicMock()
            mock_token_resp.json.return_value = mock_token_response
            mock_token_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_token_resp

            # Mock user info response
            mock_user_resp = MagicMock()
            mock_user_resp.json.return_value = mock_user_info
            mock_user_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_user_resp

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
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test T3K api_key exchange handles HTTP errors."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        mock_response = Response(
            status_code=401,
            json={"error": "invalid_api_key"},
        )
        mock_request = Request("POST", f"{t3k.base_url}/api/v1/auth/session")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = HTTPStatusError(
                "Unauthorized",
                request=mock_request,
                response=mock_response,
            )

            with pytest.raises(HTTPStatusError):
                await t3k.exchange_api_key("invalid_key")

    async def test_t3k_user_info_handles_unauthorized(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test T3K provider handles 401 Unauthorized when fetching user info."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        mock_response = Response(
            status_code=401,
            json={"error": "invalid_token"},
        )
        mock_request = Request("GET", f"{t3k.base_url}/api/v1/user")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = HTTPStatusError(
                "Unauthorized",
                request=mock_request,
                response=mock_response,
            )

            with pytest.raises(HTTPStatusError):
                await t3k.get_user_info(access_token="expired_token")

    def test_t3k_uses_custom_api_url_from_env(self, t3k_provider: OAuthProvider) -> None:
        """Test T3K provider uses custom API URL from environment."""
        from webapp.auth.providers.t3k import T3KProvider

        custom_api_url = "https://staging.tone3000.com"

        with patch.dict("os.environ", {"T3K_API_URL": custom_api_url}, clear=False):
            t3k = T3KProvider()
            assert t3k.base_url == custom_api_url

            url = t3k.build_login_url("http://localhost/callback")
            assert custom_api_url in url

    async def test_t3k_provider_returns_complete_user_profile(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test T3K provider returns all user profile fields."""
        from webapp.auth.providers.t3k import T3KProvider

        t3k = T3KProvider()

        mock_user_info = {
            "id": "t3k_12345",
            "username": "guitar_wizard",
            "email": "wizard@tone3000.com",
            "avatar_url": "https://tone3000.com/avatars/wizard.jpg",
            "created_at": "2024-01-15T10:30:00Z",
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_user_info
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            user_info = await t3k.get_user_info(access_token="valid_token")

            assert user_info["id"] == "t3k_12345"
            assert user_info["username"] == "guitar_wizard"
            assert user_info["email"] == "wizard@tone3000.com"
            assert user_info["avatar_url"] == "https://tone3000.com/avatars/wizard.jpg"
