"""Integration tests for audit logging in authentication endpoints (T117).

Tests that authentication events (login, logout, failed login) create
audit log entries via the AuditService.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import AuditLog
from webapp.adapters.persistence.models.user import OAuthProvider, User


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


class TestLoginAuditLogging:
    """Test suite for audit logging on login events."""

    async def test_successful_login_creates_audit_log(
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test that successful T3K callback creates audit log entry with event_type='login'."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        # Mock T3K provider responses
        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.exchange_api_key = AsyncMock(
                return_value={
                    "access_token": "test_access_token",
                    "refresh_token": "test_refresh_token",
                    "expires_at": "2026-12-31T23:59:59Z",
                }
            )
            mock_provider.get_user_info = AsyncMock(
                return_value={
                    "id": "12345",
                    "username": "testuser",
                    "email": "test@example.com",
                    "avatar_url": None,
                }
            )

            # Mock auth file operations
            with patch("webapp.api.v1.auth._get_auth_file") as mock_auth_file_getter:
                from unittest.mock import Mock

                mock_auth_file = mock_auth_file_getter.return_value
                mock_auth_file.save = Mock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/v1/auth/callback?api_key=test_api_key",
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
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test that failed login attempt creates audit log entry with event_type='login_failed'."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        # Mock T3K provider to fail
        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.exchange_api_key = AsyncMock(
                side_effect=Exception("API key exchange failed")
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/auth/callback?api_key=invalid_key",
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
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test that audit log captures client IP address from request."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.exchange_api_key = AsyncMock(
                return_value={
                    "access_token": "test_access_token",
                    "expires_at": "2026-12-31T23:59:59Z",
                }
            )
            mock_provider.get_user_info = AsyncMock(
                return_value={
                    "id": "12345",
                    "username": "testuser",
                    "email": "test@example.com",
                }
            )

            with patch("webapp.api.v1.auth._get_auth_file") as mock_auth_file_getter:
                mock_auth_file = mock_auth_file_getter.return_value
                mock_auth_file.save = Mock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/v1/auth/callback?api_key=test_api_key",
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
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
    ) -> None:
        """Test that audit log captures user agent from request."""
        from fastapi import FastAPI

        from webapp.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        with patch("webapp.api.v1.auth.T3KProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.exchange_api_key = AsyncMock(
                return_value={
                    "access_token": "test_access_token",
                    "expires_at": "2026-12-31T23:59:59Z",
                }
            )
            mock_provider.get_user_info = AsyncMock(
                return_value={
                    "id": "12345",
                    "username": "testuser",
                    "email": "test@example.com",
                }
            )

            with patch("webapp.api.v1.auth._get_auth_file") as mock_auth_file_getter:
                mock_auth_file = mock_auth_file_getter.return_value
                mock_auth_file.save = Mock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/v1/auth/callback?api_key=test_api_key",
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
        self, db_session: AsyncSession, t3k_provider: OAuthProvider
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

        # Mock auth file operations
        with patch("webapp.api.v1.auth._get_auth_file") as mock_auth_file_getter:
            mock_auth_file = mock_auth_file_getter.return_value
            mock_auth_file.delete = Mock()

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

                    response = await client.post("/api/v1/auth/logout")

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
