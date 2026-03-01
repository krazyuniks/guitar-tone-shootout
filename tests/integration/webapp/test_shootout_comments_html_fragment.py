"""Integration tests for shootout comments HTMX fragment endpoint.

Tests for GET /shootout/{id}/comments that renders
the comments section as a Jinja2 fragment for HTMX lazy loading.

Verifies:
- Fragment renders real comment data from DB
- Comment form with HTMX post is present
- Delete button shown only for own comments
- Empty state displayed when no comments
- data-testid attributes on interactive elements
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: "AsyncSession") -> User:
    """Create a test user for comments tests."""
    user = User(
        id=uuid4(),
        username="commentuser",
        email="comment@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: "AsyncSession") -> User:
    """Create a second user for ownership tests."""
    user = User(
        id=uuid4(),
        username="othercommenter",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_di_track(db_session: "AsyncSession", test_user: User) -> DITrack:
    """Create a test DI track for shootout."""
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
async def test_shootout(
    db_session: "AsyncSession", test_user: User, test_di_track: DITrack
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


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommentsFragmentRendersRealData:
    """Verify fragment handler wires real comment data from DB."""

    async def test_fragment_shows_existing_comment_content(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment should render actual comment text from database."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="This tone is incredible!",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "This tone is incredible!" in html

    async def test_fragment_shows_comment_author_name(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment should render the comment author's username."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Nice tone",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "commentuser" in html

    async def test_fragment_shows_multiple_comments(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment should render all comments for the shootout."""
        comment1 = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="First comment here",
        )
        comment2 = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Second comment here",
        )
        db_session.add_all([comment1, comment2])
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "First comment here" in html
        assert "Second comment here" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommentsFragmentForm:
    """Verify comment submission form is rendered with HTMX attributes."""

    async def test_fragment_has_comment_form(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment should contain a form for posting new comments."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comment-form"' in html

    async def test_fragment_form_has_textarea(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Comment form should contain a textarea for input."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comment-textarea"' in html

    async def test_fragment_form_has_submit_button(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Comment form should contain a submit button."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comment-submit"' in html

    async def test_fragment_form_uses_htmx_post(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Comment form should use hx-post for HTMX submission."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "hx-post" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommentsFragmentDeleteButton:
    """Verify delete button rendering based on comment ownership."""

    async def test_fragment_shows_delete_for_own_comment(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Delete button should appear on the user's own comments."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="My own comment",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comment-delete"' in html

    async def test_fragment_delete_uses_htmx_delete(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Delete button should use hx-delete for HTMX removal."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Delete me via HTMX",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "hx-delete" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommentsFragmentEmptyState:
    """Verify empty state rendering when no comments exist."""

    async def test_fragment_shows_empty_state(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment should show 'No comments yet' when no comments exist."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert "No comments yet" in html

    async def test_fragment_empty_state_has_data_attribute(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Empty fragment should have data-empty='true' attribute."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-empty="true"' in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommentsFragmentCommentItems:
    """Verify individual comment item rendering."""

    async def test_fragment_comment_has_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Each comment should have data-testid='comment-item'."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Testid check",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comment-item"' in html

    async def test_fragment_comment_has_timestamp(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Each comment should display a relative timestamp."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="Timestamp check",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        # Template uses {{ comment.relative_time }}, so a time string
        # like "just now" or "X seconds ago" should be present
        # The stub currently returns empty comments list, so no timestamps appear
        assert 'data-testid="comment-item"' in html
        # Verify timestamp is rendered (not empty placeholder)
        assert "ago" in html.lower() or "just now" in html.lower()

    async def test_fragment_comments_list_has_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Comments list container should have data-testid='comments-list'."""
        comment = ShootoutComment(
            shootout_id=test_shootout.id,
            user_id=test_user.id,
            content="List container check",
        )
        db_session.add(comment)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/shootout/{test_shootout.id}/comments")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="comments-list"' in html
