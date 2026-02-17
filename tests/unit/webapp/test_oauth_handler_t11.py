"""Unit tests for JWT token utilities and T3K provider (T11).

Tests for:
- JWT token creation and validation
- T3K provider URL building and API calls

Uses httpx MockTransport and monkeypatch instead of unittest.mock.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import AsyncClient, HTTPStatusError, MockTransport, Request, Response
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

    async def test_exchange_api_key_posts_to_session_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test exchange_api_key sends POST to /api/v1/auth/session."""
        from webapp.auth.providers.t3k import T3KProvider

        captured_requests: list[Request] = []

        def handler(request: Request) -> Response:
            captured_requests.append(request)
            return Response(
                200,
                json={
                    "access_token": "test_token",
                    "refresh_token": "test_refresh",
                },
            )

        transport = MockTransport(handler)

        # Monkeypatch the httpx.AsyncClient to use our transport
        original_init = AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(AsyncClient, "__init__", patched_init)

        provider = T3KProvider()
        result = await provider.exchange_api_key("test_api_key")

        assert len(captured_requests) == 1
        assert "/api/v1/auth/session" in str(captured_requests[0].url)
        assert result["access_token"] == "test_token"

    async def test_get_user_info_sends_bearer_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_user_info sends Bearer token in Authorization header."""
        from webapp.auth.providers.t3k import T3KProvider

        captured_requests: list[Request] = []

        def handler(request: Request) -> Response:
            captured_requests.append(request)
            return Response(
                200,
                json={
                    "id": "user_123",
                    "username": "testuser",
                    "email": "test@example.com",
                },
            )

        transport = MockTransport(handler)

        original_init = AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(AsyncClient, "__init__", patched_init)

        provider = T3KProvider()
        result = await provider.get_user_info("test_access_token")

        assert len(captured_requests) == 1
        assert "/api/v1/user" in str(captured_requests[0].url)
        assert captured_requests[0].headers["Authorization"] == "Bearer test_access_token"
        assert result["username"] == "testuser"

    async def test_exchange_api_key_raises_on_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test exchange_api_key raises exception on HTTP error."""
        from webapp.auth.providers.t3k import T3KProvider

        def handler(request: Request) -> Response:
            return Response(401, json={"error": "invalid_api_key"})

        transport = MockTransport(handler)

        original_init = AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(AsyncClient, "__init__", patched_init)

        provider = T3KProvider()

        with pytest.raises(HTTPStatusError):
            await provider.exchange_api_key("invalid_key")

    async def test_get_user_info_raises_on_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_user_info raises exception on HTTP error."""
        from webapp.auth.providers.t3k import T3KProvider

        def handler(request: Request) -> Response:
            return Response(401, json={"error": "invalid_token"})

        transport = MockTransport(handler)

        original_init = AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(AsyncClient, "__init__", patched_init)

        provider = T3KProvider()

        with pytest.raises(HTTPStatusError):
            await provider.get_user_info("invalid_token")
