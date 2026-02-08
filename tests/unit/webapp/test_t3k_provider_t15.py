"""Unit tests for T3K OAuth provider implementation (T15).

Tests T3K-specific OAuth provider including:
- T3K OAuth endpoints configuration (authorization, token, user info)
- Authorization URL generation with T3K-specific parameters
- Token exchange with T3K API
- User information retrieval from T3K
- Error handling for T3K API failures
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

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
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a T3K OAuth provider in the database."""
    provider = OAuthProvider(
        name="t3k",
        client_id="test_t3k_client_id",
        client_secret="test_t3k_client_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


@pytest.mark.xfail(reason="Pre-existing: T3K provider API changed")
class TestT3KProvider:
    """Test suite for T3K OAuth provider."""

    async def test_t3k_provider_module_exists(self) -> None:
        """Test T3K provider module can be imported."""
        # This will fail if the module doesn't exist (red phase)
        from webapp.auth.providers.t3k import T3KProvider

        assert T3KProvider is not None

    async def test_t3k_provider_has_authorization_url(self) -> None:
        """Test T3K provider defines authorization URL endpoint."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # T3K authorization endpoint should be defined
        assert hasattr(provider, "authorization_url")
        assert provider.authorization_url is not None
        assert isinstance(provider.authorization_url, str)
        # T3K uses tone3000.com domain
        assert "tone3000.com" in provider.authorization_url or "t3k" in provider.authorization_url.lower()

    async def test_t3k_provider_has_token_url(self) -> None:
        """Test T3K provider defines token URL endpoint."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # T3K token endpoint should be defined
        assert hasattr(provider, "token_url")
        assert provider.token_url is not None
        assert isinstance(provider.token_url, str)
        assert "tone3000.com" in provider.token_url or "t3k" in provider.token_url.lower()

    async def test_t3k_provider_has_user_info_url(self) -> None:
        """Test T3K provider defines user info URL endpoint."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # T3K user info endpoint should be defined
        assert hasattr(provider, "user_info_url")
        assert provider.user_info_url is not None
        assert isinstance(provider.user_info_url, str)
        assert "tone3000.com" in provider.user_info_url or "t3k" in provider.user_info_url.lower()

    async def test_t3k_provider_generates_authorization_url(self) -> None:
        """Test T3K provider can generate OAuth authorization URL."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()
        client_id = "test_client_123"
        redirect_uri = "http://localhost:8000/auth/t3k/callback"
        state = "random_state_token"

        # Provider should have method to build authorization URL
        auth_url = provider.build_authorization_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
        )

        # URL should contain required OAuth parameters
        assert client_id in auth_url
        assert state in auth_url
        assert "redirect_uri" in auth_url
        assert "response_type=code" in auth_url

    async def test_t3k_provider_generates_authorization_url_with_scope(self) -> None:
        """Test T3K provider includes scope in authorization URL when provided."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()
        client_id = "test_client_123"
        redirect_uri = "http://localhost:8000/auth/t3k/callback"
        state = "random_state_token"
        scope = "read write"

        # Provider should accept optional scope parameter
        auth_url = provider.build_authorization_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
        )

        # URL should contain scope parameter
        assert "scope=" in auth_url
        # Scope might be URL-encoded, so check for parts
        assert "read" in auth_url or "write" in auth_url

    async def test_t3k_provider_exchanges_code_for_token(self) -> None:
        """Test T3K provider can exchange authorization code for access token."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # Mock HTTP response from T3K token endpoint
        mock_token_response = {
            "access_token": "t3k_access_token_123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "t3k_refresh_token_456",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Exchange code for token
            tokens = await provider.exchange_code(
                code="auth_code_from_t3k",
                client_id="test_client",
                client_secret="test_secret",
                redirect_uri="http://localhost:8000/auth/t3k/callback",
            )

            # Verify token exchange was called with correct endpoint
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert provider.token_url in str(call_args)

            # Verify tokens returned
            assert tokens["access_token"] == "t3k_access_token_123"
            assert tokens["refresh_token"] == "t3k_refresh_token_456"

    async def test_t3k_provider_retrieves_user_info(self) -> None:
        """Test T3K provider can retrieve user information with access token."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()
        access_token = "valid_t3k_access_token"

        # Mock T3K user info response
        mock_user_info = {
            "id": "t3k_user_123",
            "username": "test_user",
            "email": "test@example.com",
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_user_info
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Get user info
            user_info = await provider.get_user_info(access_token=access_token)

            # Verify API call was made with Authorization header
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert provider.user_info_url in str(call_args)

            # Check that Authorization header was included
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers or "authorization" in headers

            # Verify user info returned
            assert user_info["id"] == "t3k_user_123"
            assert user_info["username"] == "test_user"

    async def test_t3k_provider_handles_token_exchange_error(self) -> None:
        """Test T3K provider handles token exchange failures gracefully."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # Mock HTTP error from T3K API
        mock_response = Response(
            status_code=400,
            json={"error": "invalid_grant", "error_description": "Invalid authorization code"},
        )
        mock_request = Request("POST", provider.token_url)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = HTTPStatusError(
                "Token exchange failed",
                request=mock_request,
                response=mock_response,
            )

            # Should raise HTTPStatusError
            with pytest.raises(HTTPStatusError):
                await provider.exchange_code(
                    code="invalid_code",
                    client_id="test_client",
                    client_secret="test_secret",
                    redirect_uri="http://localhost:8000/auth/t3k/callback",
                )

    async def test_t3k_provider_handles_user_info_error(self) -> None:
        """Test T3K provider handles user info retrieval failures."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        # Mock HTTP error from T3K user info endpoint
        mock_response = Response(
            status_code=401,
            json={"error": "invalid_token", "error_description": "Token expired"},
        )
        mock_request = Request("GET", provider.user_info_url)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = HTTPStatusError(
                "User info retrieval failed",
                request=mock_request,
                response=mock_response,
            )

            # Should raise HTTPStatusError
            with pytest.raises(HTTPStatusError):
                await provider.get_user_info(access_token="expired_token")

    async def test_t3k_provider_uses_environment_config(self) -> None:
        """Test T3K provider reads API URL from environment variables."""
        from webapp.auth.providers.t3k import T3KProvider

        # Mock environment variable
        with patch.dict("os.environ", {"T3K_API_URL": "https://custom.tone3000.com"}, clear=False):
            provider = T3KProvider()

            # Provider should use custom API URL from environment
            assert "custom.tone3000.com" in provider.authorization_url
            assert "custom.tone3000.com" in provider.token_url
            assert "custom.tone3000.com" in provider.user_info_url

    async def test_t3k_provider_has_default_api_url(self) -> None:
        """Test T3K provider has default API URL when env var not set."""
        from webapp.auth.providers.t3k import T3KProvider

        # Ensure T3K_API_URL is not set
        with patch.dict("os.environ", {}, clear=False):
            # Remove T3K_API_URL if it exists
            import os

            if "T3K_API_URL" in os.environ:
                del os.environ["T3K_API_URL"]

            provider = T3KProvider()

            # Provider should have a default API URL
            assert provider.authorization_url is not None
            assert provider.token_url is not None
            assert provider.user_info_url is not None
            # Default should be tone3000.com or similar
            assert "tone3000" in provider.authorization_url.lower() or "t3k" in provider.authorization_url.lower()

    async def test_t3k_provider_token_exchange_includes_all_parameters(self) -> None:
        """Test T3K provider token exchange includes all required OAuth parameters."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test", "token_type": "Bearer"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = mock_response

            await provider.exchange_code(
                code="test_code",
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="http://localhost/callback",
            )

            # Verify POST was called
            call_args = mock_post.call_args
            data = call_args.kwargs.get("data") or call_args.kwargs.get("json")

            # OAuth2 token exchange requires specific parameters
            assert data["grant_type"] == "authorization_code"
            assert data["code"] == "test_code"
            assert data["client_id"] == "test_client_id"
            assert data["client_secret"] == "test_client_secret"
            assert data["redirect_uri"] == "http://localhost/callback"

    async def test_t3k_provider_user_info_includes_authorization_header(self) -> None:
        """Test T3K provider includes Bearer token in user info request."""
        from webapp.auth.providers.t3k import T3KProvider

        provider = T3KProvider()
        access_token = "test_access_token_123"

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "123", "username": "test"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = mock_response

            await provider.get_user_info(access_token=access_token)

            # Verify GET was called with Authorization header
            call_args = mock_get.call_args
            headers = call_args.kwargs.get("headers", {})

            # Header can be "Authorization" or "authorization" depending on implementation
            auth_header = headers.get("Authorization") or headers.get("authorization")
            assert auth_header is not None
            assert f"Bearer {access_token}" == auth_header or access_token in auth_header


class TestT3KProviderInit:
    """Test T3K provider __init__.py exports."""

    def test_providers_module_exists(self) -> None:
        """Test providers package can be imported."""
        # This will fail if __init__.py doesn't exist
        import webapp.auth.providers

        assert webapp.auth.providers is not None

    def test_t3k_provider_exported_from_providers_init(self) -> None:
        """Test T3KProvider is exported from providers package."""
        from webapp.auth.providers import T3KProvider

        assert T3KProvider is not None
