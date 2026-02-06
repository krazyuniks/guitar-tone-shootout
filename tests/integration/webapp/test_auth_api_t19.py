"""Integration tests for Auth API endpoints (T19).

Tests for authentication API endpoints:
- GET /api/v1/auth/login - Redirects to OAuth provider
- GET /api/v1/auth/callback - Handles OAuth callback and creates session
- Token-based authentication for API requests
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity


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
    """Test suite for GET /api/v1/auth/login endpoint."""

    async def test_login_endpoint_redirects_to_oauth_provider(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/login redirects to OAuth authorization URL."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login",
                params={"provider": "t3k"},
                follow_redirects=False,
            )

            # Should return 307 redirect
            assert response.status_code == 307

            # Should redirect to OAuth provider
            location = response.headers["location"]
            assert "oauth/authorize" in location
            assert "client_id=" in location
            assert "state=" in location
            assert "redirect_uri=" in location

    async def test_login_endpoint_creates_state_parameter(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/login creates state parameter for CSRF protection."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login",
                params={"provider": "t3k"},
                follow_redirects=False,
            )

            location = response.headers["location"]
            # Extract state parameter from URL
            assert "state=" in location
            # State should be non-empty
            state_start = location.find("state=") + 6
            state_end = location.find("&", state_start)
            if state_end == -1:
                state_end = len(location)
            state = location[state_start:state_end]
            assert len(state) > 0

    async def test_login_endpoint_raises_error_for_invalid_provider(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/login returns 400 for invalid provider."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login",
                params={"provider": "nonexistent"},
                follow_redirects=False,
            )

            # Should return 400 Bad Request
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data or "error" in data

    async def test_login_endpoint_raises_error_for_disabled_provider(
        self, db_session: AsyncSession
    ) -> None:
        """Test /api/v1/auth/login returns 400 for disabled provider."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        # Create disabled provider
        disabled_provider = OAuthProvider(
            name="disabled",
            client_id="disabled_client",
            client_secret="disabled_secret",
            enabled=False,
        )
        db_session.add(disabled_provider)
        await db_session.commit()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/login",
                params={"provider": "disabled"},
                follow_redirects=False,
            )

            # Should return 400 Bad Request
            assert response.status_code == 400


class TestAuthCallbackEndpoint:
    """Test suite for GET /api/v1/auth/callback endpoint."""

    async def test_callback_endpoint_handles_oauth_callback(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback processes OAuth callback and creates user."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        # Mock OAuth token exchange and user info
        mock_token_response = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }
        mock_user_info = {
            "id": "t3k_user_789",
            "username": "callback_user",
            "email": "callback@tone3000.com",
        }

        with patch("webapp.auth.oauth.OAuthHandler.handle_callback") as mock_callback, \
             patch("webapp.auth.providers.t3k.T3KProvider.get_user_info") as mock_user_info_fn:
            mock_callback.return_value = mock_token_response
            mock_user_info_fn.return_value = mock_user_info

            async with AsyncClient(app=app, base_url="http://test") as client:
                # Simulate OAuth callback
                response = await client.get(
                    "/api/v1/auth/callback",
                    params={
                        "provider": "t3k",
                        "code": "test_auth_code",
                        "state": "test_state",
                    },
                    follow_redirects=False,
                )

                # Should successfully handle callback
                assert response.status_code in [200, 302, 307]

        # Verify user was created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].username == "callback_user"

    async def test_callback_endpoint_rejects_invalid_state(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback rejects callback with invalid state."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        with patch("webapp.auth.oauth.OAuthHandler.handle_callback") as mock_callback:
            mock_callback.side_effect = ValueError("Invalid state parameter")

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/callback",
                    params={
                        "provider": "t3k",
                        "code": "test_code",
                        "state": "invalid_state",
                    },
                    follow_redirects=False,
                )

                # Should return error response
                assert response.status_code in [400, 401, 403]

    async def test_callback_endpoint_creates_user_identity(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback creates UserIdentity for new user."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

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

        with patch("webapp.auth.oauth.OAuthHandler.handle_callback") as mock_callback, \
             patch("webapp.auth.providers.t3k.T3KProvider.get_user_info") as mock_user_info_fn:
            mock_callback.return_value = mock_token_response
            mock_user_info_fn.return_value = mock_user_info

            async with AsyncClient(app=app, base_url="http://test") as client:
                await client.get(
                    "/api/v1/auth/callback",
                    params={
                        "provider": "t3k",
                        "code": "test_code",
                        "state": "test_state",
                    },
                    follow_redirects=False,
                )

        # Verify UserIdentity was created
        result = await db_session.execute(select(UserIdentity))
        identities = result.scalars().all()
        assert len(identities) == 1
        assert identities[0].external_id == "t3k_identity_user"
        assert identities[0].provider_id == t3k_provider.id

    async def test_callback_endpoint_returns_existing_user(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /api/v1/auth/callback returns existing user on repeat login."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

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
            "id": "existing_external_id",  # Same external_id
            "username": "existing_user",
            "email": "existing@test.com",
        }

        with patch("webapp.auth.oauth.OAuthHandler.handle_callback") as mock_callback, \
             patch("webapp.auth.providers.t3k.T3KProvider.get_user_info") as mock_user_info_fn:
            mock_callback.return_value = mock_token_response
            mock_user_info_fn.return_value = mock_user_info

            async with AsyncClient(app=app, base_url="http://test") as client:
                await client.get(
                    "/api/v1/auth/callback",
                    params={
                        "provider": "t3k",
                        "code": "test_code",
                        "state": "test_state",
                    },
                    follow_redirects=False,
                )

        # Should still only have one user
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 1


class TestTokenAuthentication:
    """Test suite for token-based authentication."""

    async def test_api_requires_valid_token(
        self, db_session: AsyncSession
    ) -> None:
        """Test API endpoints require valid authentication token."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Request without token should fail
            response = await client.get("/api/v1/auth/me")

            # Should return 401 Unauthorized
            assert response.status_code == 401

    async def test_api_accepts_valid_bearer_token(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test API accepts valid Bearer token in Authorization header."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        # Create user
        user = User(
            username="token_user",
            email="token@test.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        app = FastAPI()
        app.include_router(router)

        # Mock token validation
        with patch("webapp.auth.token.validate_token") as mock_validate:
            mock_validate.return_value = user.id

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer valid_token_here"},
                )

                # Should succeed with valid token
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == str(user.id)
                assert data["username"] == "token_user"

    async def test_api_rejects_invalid_token(
        self, db_session: AsyncSession
    ) -> None:
        """Test API rejects invalid or expired tokens."""
        from webapp.api.v1.auth import router
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()
        app.include_router(router)

        with patch("webapp.auth.token.validate_token") as mock_validate:
            mock_validate.side_effect = ValueError("Invalid token")

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer invalid_token"},
                )

                # Should return 401 Unauthorized
                assert response.status_code == 401
