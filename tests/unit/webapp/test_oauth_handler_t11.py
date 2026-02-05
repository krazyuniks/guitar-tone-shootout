"""Unit tests for generic OAuth handler (T11).

Tests for provider-agnostic OAuth flow implementation including:
- Authorization URL generation with state and PKCE
- OAuth callback handling
- Token exchange with authorization code
- Error handling for invalid states and failed exchanges
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


class TestOAuthHandler:
    """Test suite for OAuth handler."""

    async def test_generate_authorization_url_creates_state_parameter(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test authorization URL generation includes state parameter for CSRF protection."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        auth_url, state = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # State should be a non-empty string
        assert state is not None
        assert isinstance(state, str)
        assert len(state) > 0

        # URL should contain state parameter
        assert f"state={state}" in auth_url

    async def test_generate_authorization_url_includes_redirect_uri(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test authorization URL includes redirect_uri parameter."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        auth_url, _ = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # URL should contain redirect_uri parameter (URL-encoded)
        assert "redirect_uri=" in auth_url
        assert "localhost" in auth_url

    async def test_generate_authorization_url_includes_client_id(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test authorization URL includes client_id from provider config."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        auth_url, _ = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # URL should contain client_id from test_provider
        assert "client_id=" in auth_url
        assert "test_client_id" in auth_url

    async def test_generate_authorization_url_raises_when_provider_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test authorization URL generation fails for non-existent provider."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        # Should raise exception when provider doesn't exist
        with pytest.raises(ValueError, match="Provider 'nonexistent' not found"):
            await handler.generate_authorization_url(
                provider_name="nonexistent",
                redirect_uri=redirect_uri,
            )

    async def test_generate_authorization_url_raises_when_provider_disabled(
        self, db_session: AsyncSession
    ) -> None:
        """Test authorization URL generation fails for disabled provider."""
        from webapp.auth.oauth import OAuthHandler

        # Create disabled provider
        disabled_provider = OAuthProvider(
            name="disabled_provider",
            client_id="disabled_client",
            client_secret="disabled_secret",
            enabled=False,
        )
        db_session.add(disabled_provider)
        await db_session.commit()

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        # Should raise exception when provider is disabled
        with pytest.raises(ValueError, match="Provider 'disabled_provider' is not enabled"):
            await handler.generate_authorization_url(
                provider_name="disabled_provider",
                redirect_uri=redirect_uri,
            )

    async def test_handle_callback_validates_state_parameter(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test callback handling validates state parameter against stored value."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)

        # Generate auth URL to create state
        redirect_uri = "http://localhost:8000/auth/callback"
        _, original_state = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # Callback with invalid state should fail
        with pytest.raises(ValueError, match="Invalid state parameter"):
            await handler.handle_callback(
                provider_name="t3k",
                code="test_auth_code",
                state="invalid_state",
                expected_state=original_state,
                redirect_uri=redirect_uri,
            )

    async def test_handle_callback_exchanges_code_for_token(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test callback handling exchanges authorization code for access token."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)

        # Generate auth URL to create state
        redirect_uri = "http://localhost:8000/auth/callback"
        _, state = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # Mock the token exchange
        mock_token_response = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token",
        }

        with patch("webapp.auth.token.TokenExchanger.exchange_code") as mock_exchange:
            mock_exchange.return_value = mock_token_response

            # Handle callback
            tokens = await handler.handle_callback(
                provider_name="t3k",
                code="test_auth_code",
                state=state,
                expected_state=state,
                redirect_uri=redirect_uri,
            )

            # Verify token exchange was called
            mock_exchange.assert_called_once()

            # Verify tokens returned
            assert tokens["access_token"] == "test_access_token"
            assert tokens["refresh_token"] == "test_refresh_token"

    async def test_handle_callback_raises_on_token_exchange_failure(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test callback handling raises exception when token exchange fails."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)

        # Generate auth URL to create state
        redirect_uri = "http://localhost:8000/auth/callback"
        _, state = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )

        # Mock token exchange failure
        mock_response = Response(
            status_code=400,
            json={"error": "invalid_grant"},
        )
        mock_request = Request("POST", "http://example.com/token")

        with patch("webapp.auth.token.TokenExchanger.exchange_code") as mock_exchange:
            mock_exchange.side_effect = HTTPStatusError(
                "Token exchange failed",
                request=mock_request,
                response=mock_response,
            )

            # Should raise exception
            with pytest.raises(HTTPStatusError):
                await handler.handle_callback(
                    provider_name="t3k",
                    code="invalid_code",
                    state=state,
                    expected_state=state,
                    redirect_uri=redirect_uri,
                )

    async def test_generate_authorization_url_includes_scope_parameter(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test authorization URL includes scope parameter when provided."""
        from webapp.auth.oauth import OAuthHandler

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"
        scope = "read write"

        auth_url, _ = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
            scope=scope,
        )

        # URL should contain scope parameter
        assert "scope=" in auth_url
        assert "read" in auth_url or "write" in auth_url

    async def test_oauth_handler_is_provider_agnostic(
        self, db_session: AsyncSession
    ) -> None:
        """Test OAuth handler works with multiple providers (T3K, Google, etc)."""
        from webapp.auth.oauth import OAuthHandler

        # Create multiple providers
        providers = [
            OAuthProvider(
                name="t3k",
                client_id="t3k_client",
                client_secret="t3k_secret",
                enabled=True,
            ),
            OAuthProvider(
                name="google",
                client_id="google_client",
                client_secret="google_secret",
                enabled=True,
            ),
        ]
        db_session.add_all(providers)
        await db_session.commit()

        handler = OAuthHandler(db_session)
        redirect_uri = "http://localhost:8000/auth/callback"

        # Should work with T3K
        t3k_url, t3k_state = await handler.generate_authorization_url(
            provider_name="t3k",
            redirect_uri=redirect_uri,
        )
        assert "t3k_client" in t3k_url
        assert t3k_state is not None

        # Should work with Google
        google_url, google_state = await handler.generate_authorization_url(
            provider_name="google",
            redirect_uri=redirect_uri,
        )
        assert "google_client" in google_url
        assert google_state is not None

        # States should be different
        assert t3k_state != google_state


class TestTokenExchanger:
    """Test suite for token exchange logic."""

    async def test_exchange_code_sends_post_request(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test token exchanger sends POST request to token endpoint."""
        from webapp.auth.token import TokenExchanger

        exchanger = TokenExchanger()

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await exchanger.exchange_code(
                token_url="https://provider.com/oauth/token",
                client_id="test_client",
                client_secret="test_secret",
                code="auth_code",
                redirect_uri="http://localhost/callback",
            )

            # Verify POST was called
            mock_post.assert_called_once()

            # Verify correct URL
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://provider.com/oauth/token"

    async def test_exchange_code_includes_required_parameters(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test token exchange includes all required OAuth parameters."""
        from webapp.auth.token import TokenExchanger

        exchanger = TokenExchanger()

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await exchanger.exchange_code(
                token_url="https://provider.com/oauth/token",
                client_id="test_client",
                client_secret="test_secret",
                code="auth_code",
                redirect_uri="http://localhost/callback",
            )

            # Verify parameters
            call_args = mock_post.call_args
            data = call_args.kwargs.get("data") or call_args.kwargs.get("json")

            assert data["grant_type"] == "authorization_code"
            assert data["code"] == "auth_code"
            assert data["client_id"] == "test_client"
            assert data["client_secret"] == "test_secret"
            assert data["redirect_uri"] == "http://localhost/callback"

    async def test_exchange_code_returns_token_response(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test token exchange returns parsed token response."""
        from webapp.auth.token import TokenExchanger

        exchanger = TokenExchanger()

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token",
            "scope": "read write",
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await exchanger.exchange_code(
                token_url="https://provider.com/oauth/token",
                client_id="test_client",
                client_secret="test_secret",
                code="auth_code",
                redirect_uri="http://localhost/callback",
            )

            # Verify all token fields returned
            assert result["access_token"] == "test_access_token"
            assert result["token_type"] == "Bearer"
            assert result["expires_in"] == 3600
            assert result["refresh_token"] == "test_refresh_token"
            assert result["scope"] == "read write"

    async def test_exchange_code_raises_on_http_error(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test token exchange raises exception on HTTP error response."""
        from webapp.auth.token import TokenExchanger

        exchanger = TokenExchanger()

        # Mock HTTP error
        mock_response = Response(
            status_code=400,
            json={"error": "invalid_grant", "error_description": "Invalid code"},
        )
        mock_request = Request("POST", "https://provider.com/oauth/token")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = HTTPStatusError(
                "HTTP error",
                request=mock_request,
                response=mock_response,
            )

            # Should raise HTTPStatusError
            with pytest.raises(HTTPStatusError):
                await exchanger.exchange_code(
                    token_url="https://provider.com/oauth/token",
                    client_id="test_client",
                    client_secret="test_secret",
                    code="invalid_code",
                    redirect_uri="http://localhost/callback",
                )

    async def test_exchange_code_handles_network_errors(
        self, db_session: AsyncSession, test_provider: OAuthProvider
    ) -> None:
        """Test token exchange handles network errors gracefully."""
        from webapp.auth.token import TokenExchanger

        exchanger = TokenExchanger()

        # Mock network error
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Network timeout")

            # Should raise exception
            with pytest.raises(Exception, match="Network timeout"):
                await exchanger.exchange_code(
                    token_url="https://provider.com/oauth/token",
                    client_id="test_client",
                    client_secret="test_secret",
                    code="auth_code",
                    redirect_uri="http://localhost/callback",
                )
