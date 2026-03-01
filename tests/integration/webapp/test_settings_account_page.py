"""Integration tests for settings/account SSR page route.

Tests for GET /settings/account - Account settings page with OAuth provider status
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.user import OAuthProvider, User, UserIdentity
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def t3k_provider(db_session: AsyncSession) -> OAuthProvider:
    """Get or create T3K OAuth provider."""
    from sqlalchemy import select

    stmt = select(OAuthProvider).where(OAuthProvider.name == "t3k")
    result = await db_session.execute(stmt)
    provider = result.scalar_one_or_none()
    if provider is None:
        provider = OAuthProvider(
            id=uuid4(),
            name="t3k",
            client_id="test-client-id",
            client_secret="test-client-secret",
            enabled=True,
        )
        db_session.add(provider)
        await db_session.commit()
        await db_session.refresh(provider)
    return provider


@pytest.mark.asyncio
@pytest.mark.integration
class TestSettingsAccountPage:
    """Test settings/account page route (/settings/account)."""

    async def test_settings_account_route_returns_html(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify GET /settings/account returns HTML page."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="settings-account-page"' in html
            assert "Account Settings" in html

    async def test_settings_account_requires_authentication(self, db_session: AsyncSession) -> None:
        """Verify page redirects to /login if not authenticated."""
        from webapp.auth.dependencies import set_user_override

        # Clear user override to simulate unauthenticated request
        set_user_override(None)

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            response = await client.get("/settings/account")

            # Should redirect to login
            assert response.status_code == 302  # Found redirect
            assert response.headers["location"] == "/login"

    async def test_settings_account_shows_username(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page shows user's username."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should show username with testid
            assert 'data-testid="settings-username"' in html
            assert test_user.username in html

    async def test_settings_account_shows_email(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page shows user's email if available."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should show email
            assert test_user.email in html

    async def test_settings_account_shows_account_creation_date(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page shows account creation date."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should show creation date (format might vary)
            # User was created with a timestamp, check if any date appears
            assert test_user.created_at is not None
            # Check for common date patterns (year at minimum)
            year = str(test_user.created_at.year)
            assert year in html or "Member since" in html or "Joined" in html

    async def test_settings_account_shows_linked_providers(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify page shows linked OAuth providers."""
        # Link T3K provider to user
        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        db_session.add(identity)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should show T3K provider
            assert 'data-testid="provider-t3k"' in html
            assert "Tone3000" in html or "T3K" in html
            assert "Linked" in html or "linked" in html

    async def test_settings_account_shows_unlink_button_for_linked_providers(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify page shows unlink button for linked providers."""
        # Link T3K provider to user
        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        db_session.add(identity)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should have unlink button with testid
            assert 'data-testid="unlink-t3k"' in html
            assert "Unlink" in html

    async def test_settings_account_disables_unlink_for_last_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify unlink button is disabled if it's the user's last provider."""
        # Link T3K provider to user (only provider)
        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        db_session.add(identity)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Unlink button should be disabled (last provider)
            # Look for disabled attribute near the unlink button
            assert "disabled" in html

    async def test_settings_account_shows_link_button_for_available_unlinked_providers(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify page shows link button for available but unlinked providers."""
        # Create another provider that's not linked
        google_provider = OAuthProvider(
            id=uuid4(),
            name="google",
            client_id="google-client-id",
            client_secret="google-client-secret",
            enabled=True,
        )
        db_session.add(google_provider)

        # Link only T3K
        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        db_session.add(identity)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # T3K should show "Linked"
            assert 'data-testid="provider-t3k"' in html

            # Google/GitHub/Facebook might show "Not linked" or "Link" button
            # (Template shows these even if not in DB as available=false)
            assert "provider-google" in html or "Google" in html

    async def test_settings_account_shows_provider_username(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify page shows provider username for linked providers."""
        # Link T3K provider to user
        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        db_session.add(identity)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should show provider username
            assert "t3k_testuser" in html

    async def test_settings_account_renders_base_layout(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify settings page extends base layout."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_settings_account_has_htmx_for_unlink(
        self,
        db_session: AsyncSession,
        test_user: User,
        t3k_provider: OAuthProvider,
    ) -> None:
        """Verify page uses HTMX for unlinking providers."""
        # Create second provider so unlink is not disabled
        google_provider = OAuthProvider(
            id=uuid4(),
            name="google",
            client_id="google-client-id",
            client_secret="google-client-secret",
            enabled=True,
        )
        db_session.add(google_provider)

        # Link both providers
        identity1 = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=t3k_provider.id,
            external_id="t3k-user-123",
            username="t3k_testuser",
        )
        identity2 = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider_id=google_provider.id,
            external_id="google-user-123",
            username="google_testuser",
        )
        db_session.add_all([identity1, identity2])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/settings/account")

            html = response.text

            # Should have HTMX delete attribute on unlink buttons
            assert "hx-delete" in html
            assert "/auth/unlink/" in html
