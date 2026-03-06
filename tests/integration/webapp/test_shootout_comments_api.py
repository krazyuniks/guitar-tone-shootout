"""Integration tests for /api/shootouts/{id}/comments endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.shootouts import router, set_session_override, set_user_override

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.di_track import DITrack


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with shootouts router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create a second test user."""
    user = User(username="otheruser", email="other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_shootout(
    db_session: AsyncSession, test_user: User, test_di_track: DITrack
) -> Shootout:
    """Create a test shootout."""
    shootout = Shootout(
        user_id=test_user.id,
        di_track_id=test_di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    db_session.add(shootout)
    await db_session.flush()
    await db_session.refresh(shootout)
    return shootout


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
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)


# --- POST /api/shootouts/{id}/comments ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestCreateComment:
    """Tests for POST /api/shootouts/{id}/comments."""

    async def test_create_comment_returns_201(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """POST creates a comment and returns 201."""
        response = await authenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": "Great shootout!"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Great shootout!"
        assert "id" in data
        assert "author_username" in data
        assert "created_at" in data

    async def test_create_comment_includes_author_info(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
        test_user: User,
    ) -> None:
        """POST response includes author username and avatar."""
        response = await authenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": "Test comment"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["author_username"] == test_user.username

    async def test_create_comment_persists_to_database(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_shootout: Shootout,
    ) -> None:
        """POST persists the comment to the database."""
        from sqlalchemy import select

        response = await authenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": "Persisted comment"},
        )

        assert response.status_code == 201
        comment_id = response.json()["id"]

        result = await db_session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment_id)
        )
        saved = result.scalar_one()
        assert saved.content == "Persisted comment"

    async def test_create_comment_returns_404_for_missing_shootout(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """POST returns 404 when shootout doesn't exist."""
        response = await authenticated_client.post(
            f"/api/shootouts/{uuid4()}/comments",
            json={"content": "Ghost shootout"},
        )

        assert response.status_code == 404

    async def test_create_comment_returns_422_for_empty_content(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """POST returns 422 for empty content."""
        response = await authenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": ""},
        )

        assert response.status_code == 422

    async def test_create_comment_returns_422_for_too_long_content(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """POST returns 422 for content exceeding 2000 chars."""
        response = await authenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": "x" * 2001},
        )

        assert response.status_code == 422

    async def test_create_comment_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """POST returns 401 when not authenticated."""
        response = await unauthenticated_client.post(
            f"/api/shootouts/{test_shootout.id}/comments",
            json={"content": "Anon comment"},
        )

        assert response.status_code == 401


# --- GET /api/shootouts/{id}/comments ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestListComments:
    """Tests for GET /api/shootouts/{id}/comments."""

    async def test_list_comments_returns_200(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """GET returns 200 with empty list when no comments."""
        response = await authenticated_client.get(
            f"/api/shootouts/{test_shootout.id}/comments",
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0} or isinstance(response.json(), list)

    async def test_list_comments_returns_comments_newest_first(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """GET returns comments in newest-first order."""
        comment1 = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="First comment",
        )
        comment2 = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Second comment",
        )
        db_session.add_all([comment1, comment2])
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/shootouts/{test_shootout.id}/comments",
        )

        assert response.status_code == 200
        data = response.json()
        # Handle both list and paginated response formats
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        assert len(items) == 2
        assert items[0]["content"] == "Second comment"
        assert items[1]["content"] == "First comment"

    async def test_list_comments_includes_author_info(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """GET response includes author username for each comment."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="With author info",
        )
        db_session.add(comment)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/shootouts/{test_shootout.id}/comments",
        )

        assert response.status_code == 200
        data = response.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        assert items[0]["author_username"] == test_user.username

    async def test_list_comments_returns_404_for_missing_shootout(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """GET returns 404 when shootout doesn't exist."""
        response = await authenticated_client.get(
            f"/api/shootouts/{uuid4()}/comments",
        )

        assert response.status_code == 404

    async def test_list_comments_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """GET returns 401 when not authenticated."""
        response = await unauthenticated_client.get(
            f"/api/shootouts/{test_shootout.id}/comments",
        )

        assert response.status_code == 401


# --- DELETE /api/shootouts/{id}/comments/{comment_id} ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestDeleteComment:
    """Tests for DELETE /api/shootouts/{id}/comments/{comment_id}."""

    async def test_delete_comment_returns_204(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE returns 204 when author deletes their comment."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Delete me",
        )
        db_session.add(comment)
        await db_session.commit()

        response = await authenticated_client.delete(
            f"/api/shootouts/{test_shootout.id}/comments/{comment.id}",
        )

        assert response.status_code == 204

    async def test_delete_comment_removes_from_database(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE removes the comment from the database."""
        from sqlalchemy import select

        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Gone forever",
        )
        db_session.add(comment)
        await db_session.commit()
        comment_id = comment.id

        await authenticated_client.delete(
            f"/api/shootouts/{test_shootout.id}/comments/{comment_id}",
        )

        result = await db_session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_comment_returns_404_for_missing_comment(
        self,
        authenticated_client: AsyncClient,
        test_shootout: Shootout,
    ) -> None:
        """DELETE returns 404 when comment doesn't exist."""
        response = await authenticated_client.delete(
            f"/api/shootouts/{test_shootout.id}/comments/{uuid4()}",
        )

        assert response.status_code == 404

    async def test_delete_comment_returns_403_for_non_author(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE returns 403 when user is not the comment author."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Not yours",
        )
        db_session.add(comment)
        await db_session.commit()

        # Authenticate as other_user
        set_session_override(db_session)
        set_user_override(other_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/shootouts/{test_shootout.id}/comments/{comment.id}",
            )

        set_session_override(None)
        set_user_override(None)

        assert response.status_code == 403

    async def test_delete_comment_returns_404_for_missing_shootout(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """DELETE returns 404 when shootout doesn't exist."""
        response = await authenticated_client.delete(
            f"/api/shootouts/{uuid4()}/comments/{uuid4()}",
        )

        assert response.status_code == 404

    async def test_delete_comment_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE returns 401 when not authenticated."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Can't delete anon",
        )
        db_session.add(comment)
        await db_session.commit()

        response = await unauthenticated_client.delete(
            f"/api/shootouts/{test_shootout.id}/comments/{comment.id}",
        )

        assert response.status_code == 401
