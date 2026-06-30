"""Integration tests for /api/shootouts/ endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.shootout import Shootout
from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.shootouts import router, set_session_override, set_user_override
from webapp.services.shootout_service import ShootoutService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with shootouts router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


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
async def test_list_shootouts_returns_users_shootouts(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test GET /api/shootouts/ returns user's shootouts."""
    service = ShootoutService(db_session)

    # Create shootouts for test user
    shootout1 = Shootout(
        user_id=test_user.id,
        name="Shootout 1",
        di_track_id=test_di_track.id,
    )
    shootout2 = Shootout(
        user_id=test_user.id,
        name="Shootout 2",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout1)
        await service.create(shootout2)

    # Request shootouts
    response = await authenticated_client.get("/api/shootouts/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {s["name"] for s in data} == {"Shootout 1", "Shootout 2"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_shootouts_does_not_return_other_users_shootouts(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test GET /api/shootouts/ does not return other users' shootouts."""
    service = ShootoutService(db_session)

    # Create shootout for test user
    user_shootout = Shootout(
        user_id=test_user.id,
        name="User Shootout",
        di_track_id=test_di_track.id,
    )
    async with db_session.begin():
        await service.create(user_shootout)

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

    # Request shootouts
    response = await authenticated_client.get("/api/shootouts/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "User Shootout"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_shootout_creates_new_shootout(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test POST /api/shootouts/ creates a new shootout."""
    payload = {
        "name": "New Shootout",
        "di_track_id": str(test_di_track.id),
        "description": "Test description",
    }

    response = await authenticated_client.post("/api/shootouts/", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Shootout"
    assert data["description"] == "Test description"
    assert "id" in data
    assert data["user_id"] == str(test_user.id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_shootout_requires_authentication(
    app: FastAPI,
    db_session: AsyncSession,
    test_di_track: DITrack,
) -> None:
    """Test POST /api/shootouts/ requires authentication."""
    # Create client without auth override
    set_session_override(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "name": "New Shootout",
            "di_track_id": str(test_di_track.id),
        }

        response = await client.post("/api/shootouts/", json=payload)

        assert response.status_code == 401

    set_session_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_shootout_validates_required_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Test POST /api/shootouts/ validates required fields."""
    # Missing name
    payload = {
        "di_track_id": "00000000-0000-0000-0000-000000000000",
    }

    response = await authenticated_client.post("/api/shootouts/", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_shootout_persists_to_database(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test POST /api/shootouts/ persists to database."""
    payload = {
        "name": "New Shootout",
        "di_track_id": str(test_di_track.id),
    }

    response = await authenticated_client.post("/api/shootouts/", json=payload)

    assert response.status_code == 201
    data = response.json()
    shootout_id = data["id"]

    # Verify in database
    service = ShootoutService(db_session)
    from uuid import UUID

    saved = await service.get_by_id(UUID(shootout_id), test_user.id)
    assert saved is not None
    assert saved.name == "New Shootout"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootout_by_id_returns_shootout(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test GET /api/shootouts/{id} returns shootout details."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
        description="Test description",
    )

    async with db_session.begin():
        await service.create(shootout)

    response = await authenticated_client.get(f"/api/shootouts/{shootout.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(shootout.id)
    assert data["name"] == "Test Shootout"
    assert data["description"] == "Test description"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootout_by_id_returns_404_for_missing(
    authenticated_client: AsyncClient,
) -> None:
    """Test GET /api/shootouts/{id} returns 404 for non-existent shootout."""
    from uuid import uuid4

    response = await authenticated_client.get(f"/api/shootouts/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootout_by_id_returns_404_for_other_users_shootout(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_di_track: DITrack,
) -> None:
    """Test GET /api/shootouts/{id} returns 404 for other user's shootout."""
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
    response = await authenticated_client.get(f"/api/shootouts/{other_shootout.id}")

    # Returns 404 to avoid leaking existence
    assert response.status_code == 404
