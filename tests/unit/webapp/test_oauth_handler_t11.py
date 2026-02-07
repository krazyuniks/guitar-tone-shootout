"""Unit tests for JWT token utilities and T3K provider (T11).

Tests for:
- JWT token creation and validation
- T3K provider URL building and API calls
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import HTTPStatusError, Request, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

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
async def test_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a test OAuth provider."""
    provider = OAuthProvider(
        name="t3k",
        client_id="test_client_id",
        client_secret="test_client_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestJWTToken:
    """Test suite for JWT token utilities."""

    def test_create_access_token_returns_string(self) -> None:
        """Test create_access_token returns a non-empty string."""
        from webapp.auth.token import create_access_token

        user_id = uuid4()
        token = create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token_returns_payload(self) -> None:
        """Test decode_access_token returns the original payload."""
        from webapp.auth.token import create_access_token, decode_access_token

        user_id = uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)

        assert payload["sub"] == str(user_id)
        assert "iat" in payload
        assert "exp" in payload

    def test_get_user_id_from_token_returns_uuid(self) -> None:
        """Test get_user_id_from_token extracts UUID from token."""
        from webapp.auth.token import create_access_token, get_user_id_from_token

        user_id = uuid4()
        token = create_access_token(user_id)
        result = get_user_id_from_token(token)

        assert result == user_id

    def test_decode_invalid_token_raises(self) -> None:
        """Test decode_access_token raises on invalid token."""
        import jwt

        from webapp.auth.token import decode_access_token

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("invalid_token")

    def test_token_contains_expiry(self) -> None:
        """Test JWT token has an expiry claim."""
        from webapp.auth.token import create_access_token, decode_access_token

        user_id = uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)

        assert "exp" in payload
        assert payload["exp"] > payload["iat"]


class TestT3KProvider:
    """Test suite for T3K authentication provider."""

    def test_build_login_url_includes_redirect(self) -> None:
        """Test build_login_url includes redirect_url parameter."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()
        callback = "http://localhost:9000/api/v1/auth/callback"

        url = provider.build_login_url(callback)

        assert "tone3000.com" in url
        assert "redirect_url=" in url
        assert callback in url

    async def test_exchange_api_key_posts_to_session_endpoint(self) -> None:
        """Test exchange_api_key sends POST to /api/v1/auth/session."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await provider.exchange_api_key("test_api_key")

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/api/v1/auth/session" in call_args[0][0]
            assert call_args[1]["json"] == {"api_key": "test_api_key"}
            assert result["access_token"] == "test_token"

    async def test_get_user_info_sends_bearer_token(self) -> None:
        """Test get_user_info sends Bearer token in Authorization header."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await provider.get_user_info("test_access_token")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/api/v1/user" in call_args[0][0]
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_access_token"
            assert result["username"] == "testuser"

    async def test_exchange_api_key_raises_on_http_error(self) -> None:
        """Test exchange_api_key raises exception on HTTP error."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        mock_response = Response(
            status_code=401,
            json={"error": "invalid_api_key"},
        )
        mock_request = Request("POST", "https://www.tone3000.com/api/v1/auth/session")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = HTTPStatusError(
                "Unauthorized",
                request=mock_request,
                response=mock_response,
            )

            with pytest.raises(HTTPStatusError):
                await provider.exchange_api_key("invalid_key")

    async def test_get_user_info_raises_on_http_error(self) -> None:
        """Test get_user_info raises exception on HTTP error."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        mock_response = Response(
            status_code=401,
            json={"error": "invalid_token"},
        )
        mock_request = Request("GET", "https://www.tone3000.com/api/v1/user")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = HTTPStatusError(
                "Unauthorized",
                request=mock_request,
                response=mock_response,
            )

            with pytest.raises(HTTPStatusError):
                await provider.get_user_info("invalid_token")
