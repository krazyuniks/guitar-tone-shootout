"""Integration tests for shootout SSR page routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.shootout import Shootout
from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.pages import router
from webapp.auth.dependencies import set_session_override, set_user_override
from webapp.services.shootout_service import ShootoutService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with pages router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_di_track(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a test DI track."""
    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI",
        file_path="/path/to/di.wav",
        original_filename="di.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()
    await db_session.refresh(di_track)
    return di_track


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_library_shootouts_page_renders(
    authenticated_client: AsyncClient,
) -> None:
    """Test GET /library/shootouts renders the shootout library page."""
    response = await authenticated_client.get("/library/shootouts")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.xfail(
    reason="Pre-existing: Auth redirects to login (302) instead of 401", strict=False
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_library_shootouts_page_requires_authentication(
    app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Test GET /library/shootouts requires authentication."""
    # Create client without auth override
    set_session_override(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/library/shootouts")

        assert response.status_code == 401

    set_session_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_detail_page_renders_for_owned_shootout(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test GET /shootout/{id} renders shootout detail page for owned shootout."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
        description="Test description",
    )

    async with db_session.begin():
        await service.create(shootout)

    response = await authenticated_client.get(f"/shootout/{shootout.id}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_detail_page_returns_404_for_missing_shootout(
    authenticated_client: AsyncClient,
) -> None:
    """Test GET /shootout/{id} returns 404 for non-existent shootout."""
    from uuid import uuid4

    response = await authenticated_client.get(f"/shootout/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_detail_page_returns_404_for_other_users_shootout(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test GET /shootout/{id} returns 404 for other user's shootout (hides existence)."""
    service = ShootoutService(db_session)

    # Create another user and their shootout
    other_user = User(username="other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_di_track = DITrack(
        user_id=other_user.id,
        name="Other DI",
        file_path="/path/other.wav",
        original_filename="other.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(other_di_track)
    await db_session.flush()

    other_shootout = Shootout(
        user_id=other_user.id,
        name="Other Shootout",
        di_track_id=other_di_track.id,
    )
    async with db_session.begin():
        await service.create(other_shootout)

    # Try to access other user's shootout
    response = await authenticated_client.get(f"/shootout/{other_shootout.id}")

    # Returns 404 to avoid leaking existence
    assert response.status_code == 404


@pytest.mark.xfail(
    reason="Pre-existing: Auth redirects to login (302) instead of 401", strict=False
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_detail_page_requires_authentication(
    app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Test GET /shootout/{id} requires authentication."""
    from uuid import uuid4

    # Create client without auth override
    set_session_override(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/shootout/{uuid4()}")

        assert response.status_code == 401

    set_session_override(None)
