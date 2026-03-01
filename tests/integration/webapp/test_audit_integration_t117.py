"""Integration tests for audit logging in authentication endpoints (T117).

Tests that authentication events (login, logout, failed login) create
audit log entries via the AuditService.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from webapp.adapters.persistence.models.job import AuditLog
from webapp.adapters.persistence.models.user import OAuthProvider, User


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


class FakeAuthFile:
    """Test double for AuthFilePersistence."""

    def __init__(self) -> None:
        self.save_calls: list[dict[str, Any]] = []
        self.delete_calls: int = 0

    def save(self, data: dict[str, Any]) -> None:
        self.save_calls.append(data)

    def delete(self) -> None:
        self.delete_calls += 1

    def load(self) -> None:
        return None


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


class TestLoginAuditLogging:
    """Test suite for audit logging on login events."""

    async def test_successful_login_creates_audit_log(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that successful T3K callback creates audit log entry with event_type='login'."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": "2026-12-31T23:59:59Z",
            },
            user_info={
                "id": "12345",
                "username": "testuser",
                "email": "test@example.com",
                "avatar_url": None,
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        fake_auth_file = FakeAuthFile()
        monkeypatch.setattr("webapp.api.v1.auth._get_auth_file", lambda: fake_auth_file)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback?api_key=test_api_key",
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify audit log was created
            result = await db_session.execute(select(AuditLog))
            logs = result.scalars().all()

            assert len(logs) == 1
            assert logs[0].action == "login"
            assert logs[0].resource_type == "user"
            assert logs[0].user_id is not None

    async def test_failed_login_creates_audit_log(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that failed login attempt creates audit log entry with event_type='login_failed'."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            exchange_error=Exception("API key exchange failed"),
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback?api_key=invalid_key",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "error=callback_failed" in response.headers["location"]

            # Verify audit log was created for failed attempt
            result = await db_session.execute(select(AuditLog))
            logs = result.scalars().all()

            assert len(logs) == 1
            assert logs[0].action == "login_failed"
            assert logs[0].resource_type == "user"

    async def test_audit_log_captures_ip_address(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that audit log captures client IP address from request."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_access_token",
                "expires_at": "2026-12-31T23:59:59Z",
            },
            user_info={
                "id": "12345",
                "username": "testuser",
                "email": "test@example.com",
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        fake_auth_file = FakeAuthFile()
        monkeypatch.setattr("webapp.api.v1.auth._get_auth_file", lambda: fake_auth_file)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback?api_key=test_api_key",
                headers={"X-Forwarded-For": "192.168.1.100"},
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify IP address was captured
            result = await db_session.execute(select(AuditLog))
            logs = result.scalars().all()

            assert len(logs) == 1
            # IP should be captured (specific extraction logic depends on implementation)
            assert logs[0].ip_address is not None

    async def test_audit_log_captures_user_agent(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that audit log captures user agent from request."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        fake_provider = FakeT3KProvider(
            token_response={
                "access_token": "test_access_token",
                "expires_at": "2026-12-31T23:59:59Z",
            },
            user_info={
                "id": "12345",
                "username": "testuser",
                "email": "test@example.com",
            },
        )
        monkeypatch.setattr("webapp.api.v1.auth.T3KProvider", lambda: fake_provider)

        fake_auth_file = FakeAuthFile()
        monkeypatch.setattr("webapp.api.v1.auth._get_auth_file", lambda: fake_auth_file)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/auth/callback?api_key=test_api_key",
                headers={"User-Agent": "Mozilla/5.0 (Test Browser)"},
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify user agent was captured
            result = await db_session.execute(select(AuditLog))
            logs = result.scalars().all()

            assert len(logs) == 1
            assert logs[0].user_agent is not None


class TestLogoutAuditLogging:
    """Test suite for audit logging on logout events."""

    async def test_logout_creates_audit_log(
        self,
        db_session: AsyncSession,
        t3k_provider: OAuthProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that POST /logout creates audit log entry if logout endpoint exists."""
        from uuid import uuid4

        from fastapi import FastAPI

        from webapp.api.v1.auth import router
        from webapp.auth.token import JWT_COOKIE_NAME, create_access_token

        app = FastAPI()
        app.include_router(router)

        # Create a test user
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Create JWT for the user
        jwt_token = create_access_token(user.id)

        fake_auth_file = FakeAuthFile()
        monkeypatch.setattr("webapp.api.v1.auth._get_auth_file", lambda: fake_auth_file)

        # Override the session dependency
        from webapp.auth.dependencies import set_session_override, set_user_override

        set_session_override(db_session)
        set_user_override(user)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Set the JWT cookie
                client.cookies.set(JWT_COOKIE_NAME, jwt_token)

                response = await client.post("/auth/logout")

                assert response.status_code == 200

                # Verify audit log was created for logout
                result = await db_session.execute(select(AuditLog))
                logs = result.scalars().all()

                # This test will FAIL if logout doesn't log audit events
                # The implementation must add audit logging to the logout endpoint
                assert len(logs) >= 1
                logout_logs = [log for log in logs if log.action == "logout"]
                assert len(logout_logs) == 1
                assert logout_logs[0].resource_type == "user"
                assert logout_logs[0].user_id == user.id
        finally:
            set_session_override(None)
            set_user_override(None)
