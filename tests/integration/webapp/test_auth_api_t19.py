"""Integration tests for Auth API endpoints (T19).

Tests for authentication API endpoints:
- GET /auth/login/t3k - Redirects to T3K login
- GET /auth/callback - Handles T3K callback with api_key
- GET /auth/me - Returns current user info (JWT cookie)
- POST /auth/logout - Clears JWT cookie
- GET /auth/status - Auth file status
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity
from webapp.auth.token import JWT_COOKIE_NAME, create_access_token


class FakeT3KProvider:
    """Test double for T3KProvider with configurable responses."""

    def __init__(
        self,
        token_response: dict[str, Any] | None = None,
        user_info: dict[str, Any] | None = None,
        exchange_error: Exception | None = None,
    ) -> None:
        self.token_response = token_response or {}
        self.user_info_response = user_info or {}
        self.exchange_error = exchange_error
        self.base_url = "https://www.tone3000.com"

    def build_login_url(self, callback_url: str) -> str:
        return f"{self.base_url}/api/auth?redirect_url={callback_url}"

    async def exchange_api_key(self, api_key: str) -> dict[str, Any]:
        if self.exchange_error:
            raise self.exchange_error
        return self.token_response

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        return self.user_info_response


@pytest.fixture
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Create a T3K OAuth provider."""
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    provider = OAuthProvider(
        name=f"t3k_{suffix}",
        client_id="test_client_id",
        client_secret="test_client_secret",
        enabled=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestAuthLoginEndpoint:
    """Test suite for GET /auth/login/t3k endpoint."""

    async def test_login_t3k_redirects_to_tone3000(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /auth/login/t3k redirects to T3K login page."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/login/t3k",
                follow_redirects=False,
            )

            assert response.status_code == 307
            location = response.headers["location"]
            assert "tone3000.com" in location
            assert "redirect_url=" in location

    async def test_login_t3k_preserves_next_param(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /auth/login/t3k preserves ?next= in temp cookie."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/login/t3k?next=/library/chains",
                follow_redirects=False,
            )

            assert response.status_code == 307
            # Check that gts_next cookie was set
            cookies = response.cookies
            assert "gts_next" in cookies or any("gts_next" in str(h) for h in response.headers.raw)

    async def test_login_unknown_provider_returns_404(self, db_session: AsyncSession) -> None:
        """Test /auth/login/{provider} returns 404 for unknown providers."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/login/google",
                follow_redirects=False,
            )

            assert response.status_code == 404


class TestAuthCallbackEndpoint:
    """Test suite for GET /auth/callback endpoint."""

    async def test_callback_with_api_key_creates_user(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test /auth/callback processes T3K api_key and creates user."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            user_info={
                "id": "t3k_user_789",
                "username": "callback_user",
                "email": "callback@tone3000.com",
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback?api_key=test_key",
                follow_redirects=False,
            )

            # Should redirect after successful callback
            assert response.status_code == 302
            # Should set JWT cookie
            assert JWT_COOKIE_NAME in response.cookies or any(
                JWT_COOKIE_NAME in str(h) for h in response.headers.raw
            )

        # Verify user was created (filter by username to avoid matching existing DB rows)
        result = await db_session.execute(select(User).where(User.username == "callback_user"))
        users = result.scalars().all()
        assert len(users) >= 1
        assert users[0].username == "callback_user"

    async def test_callback_without_api_key_redirects_to_login(
        self, db_session: AsyncSession
    ) -> None:
        """Test /auth/callback without api_key redirects to login with error."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "login" in response.headers["location"]
            assert "error" in response.headers["location"]

    async def test_callback_creates_user_identity(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test /auth/callback creates UserIdentity for new user."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_token",
                "refresh_token": "test_refresh",
            },
            user_info={
                "id": "t3k_identity_user",
                "username": "identity_test",
                "email": "identity@test.com",
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get(
                "/auth/callback?api_key=test_key",
                follow_redirects=False,
            )

        # Verify UserIdentity was created (filter by external_id to avoid matching existing DB rows)
        result = await db_session.execute(
            select(UserIdentity).where(UserIdentity.external_id == "t3k_identity_user")
        )
        identities = result.scalars().all()
        assert len(identities) >= 1
        assert identities[0].external_id == "t3k_identity_user"

    async def test_callback_returns_existing_user(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test /auth/callback returns existing user on repeat login."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

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

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_token",
                "refresh_token": "test_refresh",
            },
            user_info={
                "id": "existing_external_id",
                "username": "existing_user",
                "email": "existing@test.com",
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get(
                "/auth/callback?api_key=test_key",
                follow_redirects=False,
            )

        # The existing user should still exist (one copy for "existing_user" external_id)
        result = await db_session.execute(select(User).where(User.username == "existing_user"))
        users = result.scalars().all()
        assert len(users) >= 1


class TestTokenAuthentication:
    """Test suite for JWT cookie authentication."""

    async def test_me_requires_authentication(self, db_session: AsyncSession) -> None:
        """Test /auth/me returns 401 without JWT cookie."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/me")
            assert response.status_code == 401

    async def test_me_returns_user_with_valid_jwt(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test /auth/me returns user info with valid JWT cookie."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

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
                "/auth/me",
                cookies={JWT_COOKIE_NAME: token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(user.id)
            assert data["username"] == "token_user"

    async def test_me_rejects_invalid_jwt(self, db_session: AsyncSession) -> None:
        """Test /auth/me rejects invalid JWT cookie."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/me",
                cookies={JWT_COOKIE_NAME: "invalid_token"},
            )
            assert response.status_code == 401
