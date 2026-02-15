"""Integration tests for Tag CRUD API (T131).

Tests TagService and /api/v1/tags/ endpoints.
Tags are user-created labels, unique per user, normalised to lowercase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.user import User
from webapp.api.v1.tags import router
from webapp.auth.dependencies import (
    set_session_override,
    set_user_override,
)
from webapp.services.tag_service import TagService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with tags router."""
    from fastapi import FastAPI

    from webapp.exception_handlers import app_exception_handler
    from webapp.exceptions import AppException

    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(AppException, app_exception_handler)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="taguser",
        email="taguser@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for isolation tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


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

    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def unauthenticated_client(
    app: FastAPI,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    set_session_override(None)
    set_user_override(None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# Service Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestTagService:
    """Test TagService CRUD operations."""

    async def test_create_tag(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test creating a tag persists it to the database."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="blues")

        assert tag.name == "blues"
        assert tag.user_id == test_user.id
        assert tag.id is not None

    async def test_create_tag_normalises_to_lowercase(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that tag names are normalised to lowercase on create."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="High-Gain")

        assert tag.name == "high-gain"

    async def test_create_tag_strips_whitespace(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that tag names are stripped of leading/trailing whitespace."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="  metal  ")

        assert tag.name == "metal"

    async def test_create_duplicate_tag_raises_conflict(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that creating a duplicate tag name for same user raises ConflictError."""
        from webapp.exceptions import ConflictError

        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="metal")

        with pytest.raises(ConflictError):
            async with db_session.begin():
                await service.create(user_id=test_user.id, name="metal")

    async def test_create_duplicate_tag_case_insensitive(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that duplicate detection is case-insensitive."""
        from webapp.exceptions import ConflictError

        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="Metal")

        with pytest.raises(ConflictError):
            async with db_session.begin():
                await service.create(user_id=test_user.id, name="METAL")

    async def test_same_tag_name_different_users_allowed(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test that different users can have tags with the same name."""
        service = TagService(db_session)

        async with db_session.begin():
            tag1 = await service.create(user_id=test_user.id, name="metal")

        async with db_session.begin():
            tag2 = await service.create(user_id=other_user.id, name="metal")

        assert tag1.name == "metal"
        assert tag2.name == "metal"
        assert tag1.user_id != tag2.user_id

    async def test_get_by_user_returns_users_tags(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_by_user returns only the specified user's tags."""
        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="blues")
            await service.create(user_id=test_user.id, name="jazz")

        tags = await service.get_by_user(user_id=test_user.id)

        assert len(tags) == 2
        tag_names = {t.name for t in tags}
        assert tag_names == {"blues", "jazz"}

    async def test_get_by_user_excludes_other_users_tags(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test get_by_user does not return other users' tags."""
        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="blues")
            await service.create(user_id=other_user.id, name="jazz")

        tags = await service.get_by_user(user_id=test_user.id)

        assert len(tags) == 1
        assert tags[0].name == "blues"

    async def test_get_by_user_empty(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_by_user returns empty list when user has no tags."""
        service = TagService(db_session)

        tags = await service.get_by_user(user_id=test_user.id)

        assert tags == []

    async def test_delete_tag(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test deleting a tag removes it from the database."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="blues")

        tag_id = tag.id

        async with db_session.begin():
            await service.delete(tag_id=tag_id, user_id=test_user.id)

        tags = await service.get_by_user(user_id=test_user.id)
        assert len(tags) == 0

    async def test_delete_tag_wrong_user_raises_not_found(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test deleting another user's tag raises NotFoundError (not 403)."""
        from webapp.exceptions import NotFoundError

        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="blues")

        with pytest.raises(NotFoundError):
            async with db_session.begin():
                await service.delete(tag_id=tag.id, user_id=other_user.id)

    async def test_delete_nonexistent_tag_raises_not_found(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test deleting a non-existent tag raises NotFoundError."""
        from webapp.exceptions import NotFoundError

        service = TagService(db_session)

        with pytest.raises(NotFoundError):
            async with db_session.begin():
                await service.delete(tag_id=uuid4(), user_id=test_user.id)


# API Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestTagAPI:
    """Test /api/v1/tags/ endpoints."""

    async def test_list_tags_returns_users_tags(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/tags returns current user's tags."""
        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="blues")
            await service.create(user_id=test_user.id, name="jazz")

        response = await authenticated_client.get("/api/v1/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        tag_names = {t["name"] for t in data}
        assert tag_names == {"blues", "jazz"}

    async def test_list_tags_excludes_other_users(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test GET /api/v1/tags only returns authenticated user's tags."""
        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="blues")
            await service.create(user_id=other_user.id, name="jazz")

        response = await authenticated_client.get("/api/v1/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "blues"

    async def test_create_tag_success(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test POST /api/v1/tags creates a tag."""
        response = await authenticated_client.post(
            "/api/v1/tags",
            json={"name": "metal"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "metal"
        assert "id" in data
        assert data["user_id"] == str(test_user.id)

    async def test_create_tag_normalises_name(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test POST /api/v1/tags normalises tag name to lowercase."""
        response = await authenticated_client.post(
            "/api/v1/tags",
            json={"name": "High-Gain"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "high-gain"

    async def test_create_tag_duplicate_returns_409(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test POST /api/v1/tags returns 409 for duplicate tag name."""
        await authenticated_client.post(
            "/api/v1/tags",
            json={"name": "metal"},
        )

        response = await authenticated_client.post(
            "/api/v1/tags",
            json={"name": "metal"},
        )

        assert response.status_code == 409

    async def test_delete_tag_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test DELETE /api/v1/tags/{id} deletes the tag."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=test_user.id, name="blues")

        response = await authenticated_client.delete(f"/api/v1/tags/{tag.id}")

        assert response.status_code == 204

        # Verify deletion
        tags = await service.get_by_user(user_id=test_user.id)
        assert len(tags) == 0

    async def test_delete_tag_not_found(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test DELETE /api/v1/tags/{id} returns 404 for non-existent tag."""
        response = await authenticated_client.delete(f"/api/v1/tags/{uuid4()}")

        assert response.status_code == 404

    async def test_delete_tag_other_user_returns_404(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Test DELETE returns 404 for tags owned by other users (no existence leak)."""
        service = TagService(db_session)

        async with db_session.begin():
            tag = await service.create(user_id=other_user.id, name="blues")

        response = await authenticated_client.delete(f"/api/v1/tags/{tag.id}")

        assert response.status_code == 404

    async def test_list_tags_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/tags requires authentication."""
        response = await unauthenticated_client.get("/api/v1/tags")

        assert response.status_code == 401

    async def test_create_tag_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test POST /api/v1/tags requires authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/tags",
            json={"name": "metal"},
        )

        assert response.status_code == 401

    async def test_delete_tag_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test DELETE /api/v1/tags/{id} requires authentication."""
        response = await unauthenticated_client.delete(f"/api/v1/tags/{uuid4()}")

        assert response.status_code == 401

    async def test_list_tags_response_schema(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/tags response matches expected schema."""
        service = TagService(db_session)

        async with db_session.begin():
            await service.create(user_id=test_user.id, name="blues")

        response = await authenticated_client.get("/api/v1/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        tag = data[0]
        assert "id" in tag
        assert "name" in tag
        assert "user_id" in tag
        assert "created_at" in tag
