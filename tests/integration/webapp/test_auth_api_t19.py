"""Integration tests for Auth API endpoints (T19).

Tests for authentication API endpoints:
- GET /api/v1/auth/login/t3k - Redirects to T3K login
- GET /api/v1/auth/callback - Handles T3K callback with api_key
- GET /api/v1/auth/me - Returns current user info (JWT cookie)
- POST /api/v1/auth/logout - Clears JWT cookie
- GET /api/v1/auth/status - Auth file status
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity
from webapp.auth.token import create_access_token, JWT_COOKIE_NAME


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
    """Create a T3K OAuth provider."""
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


class TestAuthLoginEndpoint:
    """Test suite for GET /api/v1/auth/login/t3k endpoint."""

    async def test_login_t3k_redirects_to_tone3000(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/login/t3k redirects to T3K login page."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login/t3k",
                follow_redirects=False,
            )

            assert response.status_code == 307
            location = response.headers["location"]
            assert "tone3000.com" in location
            assert "redirect_url=" in location

    async def test_login_t3k_preserves_next_param(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/login/t3k preserves ?next= in temp cookie."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login/t3k?next=/library/chains",
                follow_redirects=False,
            )

            assert response.status_code == 307
            # Check that gts_next cookie was set
            cookies = response.cookies
            assert "gts_next" in cookies or any(
                "gts_next" in str(h) for h in response.headers.raw
            )

    async def test_login_unknown_provider_returns_404(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/login/{provider} returns 404 for unknown providers."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login/google",
                follow_redirects=False,
            )

            assert response.status_code == 404


class TestAuthCallbackEndpoint:
    """Test suite for GET /api/v1/auth/callback endpoint."""

    async def test_callback_with_api_key_creates_user(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback processes T3K api_key and creates user."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_token_response = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        mock_user_info = {
            "id": "t3k_user_789",
            "username": "callback_user",
            "email": "callback@tone3000.com",
        }

        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.exchange_api_key = AsyncMock(return_value=mock_token_response)
            instance.get_user_info = AsyncMock(return_value=mock_user_info)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/callback?api_key=test_key",
                    follow_redirects=False,
                )

                # Should redirect after successful callback
                assert response.status_code == 302
                # Should set JWT cookie
                assert JWT_COOKIE_NAME in response.cookies or any(
                    JWT_COOKIE_NAME in str(h) for h in response.headers.raw
                )

        # Verify user was created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].username == "callback_user"

    async def test_callback_without_api_key_redirects_to_login(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/callback without api_key redirects to login with error."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/callback",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "login" in response.headers["location"]
            assert "error" in response.headers["location"]

    async def test_callback_creates_user_identity(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback creates UserIdentity for new user."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_token_response = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }
        mock_user_info = {
            "id": "t3k_identity_user",
            "username": "identity_test",
            "email": "identity@test.com",
        }

        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.exchange_api_key = AsyncMock(return_value=mock_token_response)
            instance.get_user_info = AsyncMock(return_value=mock_user_info)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.get(
                    "/api/v1/auth/callback?api_key=test_key",
                    follow_redirects=False,
                )

        # Verify UserIdentity was created
        result = await db_session.execute(select(UserIdentity))
        identities = result.scalars().all()
        assert len(identities) == 1
        assert identities[0].external_id == "t3k_identity_user"
        assert identities[0].provider_id == t3k_provider.id

    async def test_callback_returns_existing_user(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback returns existing user on repeat login."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        # Create existing user and identity
        user = User(
            username="existing_user",
            email="existing@test.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider_id=t3k_provider.id,
            external_id="existing_external_id",
            username="existing_user",
        )
        db_session.add(identity)
        await db_session.commit()

        app = FastAPI()
        app.include_router(router)

        mock_token_response = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }
        mock_user_info = {
            "id": "existing_external_id",
            "username": "existing_user",
            "email": "existing@test.com",
        }

        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.exchange_api_key = AsyncMock(return_value=mock_token_response)
            instance.get_user_info = AsyncMock(return_value=mock_user_info)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.get(
                    "/api/v1/auth/callback?api_key=test_key",
                    follow_redirects=False,
                )

        # Should still only have one user
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 1


class TestTokenAuthentication:
    """Test suite for JWT cookie authentication."""

    async def test_me_requires_authentication(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/me returns 401 without JWT cookie."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/me")
            assert response.status_code == 401

    async def test_me_returns_user_with_valid_jwt(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/me returns user info with valid JWT cookie."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        # Create user
        user = User(
            username="token_user",
            email="token@test.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Create JWT
        token = create_access_token(user.id)

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                cookies={JWT_COOKIE_NAME: token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(user.id)
            assert data["username"] == "token_user"

    async def test_me_rejects_invalid_jwt(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/me rejects invalid JWT cookie."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                cookies={JWT_COOKIE_NAME: "invalid_token"},
            )
            assert response.status_code == 401
