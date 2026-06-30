"""Unit tests for ShootoutCommentRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.shootout import (
    DITrack,
    Shootout,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def user(session: AsyncSession) -> User:
    """Create a test user."""
    _sfx = uuid4().hex[:8]
    user = User(username=f"testuser_{_sfx}", email=f"test_{_sfx}@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    """Create a second test user."""
    _sfx = uuid4().hex[:8]
    user = User(username=f"otheruser_{_sfx}", email=f"other_{_sfx}@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def shootout(session: AsyncSession, user: User) -> Shootout:
    """Create a test shootout."""
    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()
    return shootout


@pytest.fixture
def repository(session: AsyncSession) -> ShootoutCommentRepository:
    """Create a ShootoutCommentRepository instance."""
    return ShootoutCommentRepository(session)


class TestShootoutCommentRepositoryCreate:
    """Tests for creating comments via the repository."""

    @pytest.mark.asyncio
    async def test_create_comment_persists_to_db(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.create persists a comment and returns it with user loaded."""
        comment = await repository.create(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Great shootout!",
        )

        assert comment.id is not None
        assert comment.shootout_id == shootout.id
        assert comment.user_id == user.id
        assert comment.content == "Great shootout!"

        # Verify persisted in DB
        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment.id)
        )
        saved = result.scalar_one()
        assert saved.content == "Great shootout!"


class TestShootoutCommentRepositoryListByShootout:
    """Tests for listing comments by shootout."""

    @pytest.mark.asyncio
    async def test_list_by_shootout_returns_comments_newest_first(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.list_by_shootout returns comments ordered newest first."""
        # Create comments manually to control order
        comment1 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="First comment",
        )
        comment2 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Second comment",
        )
        session.add_all([comment1, comment2])
        await session.commit()

        comments = await repository.list_by_shootout(shootout.id)

        assert len(comments) == 2
        # Newest first means second comment appears first
        assert comments[0].content == "Second comment"
        assert comments[1].content == "First comment"

    @pytest.mark.asyncio
    async def test_list_by_shootout_returns_empty_for_no_comments(
        self,
        repository: ShootoutCommentRepository,
        shootout: Shootout,
    ) -> None:
        """Repository.list_by_shootout returns empty list when no comments exist."""
        comments = await repository.list_by_shootout(shootout.id)
        assert comments == []

    @pytest.mark.asyncio
    async def test_list_by_shootout_does_not_return_other_shootout_comments(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.list_by_shootout only returns comments for the given shootout."""
        # Create a second shootout
        di_track = DITrack(
            user_id=user.id,
            name="Other DI Track",
            file_path="/path/to/other.wav",
            original_filename="other.wav",
            duration_seconds=30.0,
            sample_rate=48000,
        )
        session.add(di_track)
        await session.commit()

        other_shootout = Shootout(
            user_id=user.id,
            di_track_id=di_track.id,
            name="Other Shootout",
            status=ShootoutStatus.PENDING,
        )
        session.add(other_shootout)
        await session.commit()

        # Add comment to the other shootout
        other_comment = ShootoutComment(
            shootout_id=other_shootout.id,
            user_id=user.id,
            content="Other shootout comment",
        )
        # Add comment to our shootout
        our_comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Our shootout comment",
        )
        session.add_all([other_comment, our_comment])
        await session.commit()

        comments = await repository.list_by_shootout(shootout.id)

        assert len(comments) == 1
        assert comments[0].content == "Our shootout comment"

    @pytest.mark.asyncio
    async def test_list_by_shootout_supports_pagination(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.list_by_shootout supports limit and offset."""
        for i in range(5):
            comment = ShootoutComment(
                shootout_id=shootout.id,
                user_id=user.id,
                content=f"Comment {i}",
            )
            session.add(comment)
        await session.commit()

        # Get first page
        page1 = await repository.list_by_shootout(shootout.id, limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = await repository.list_by_shootout(shootout.id, limit=2, offset=2)
        assert len(page2) == 2

        # Ensure no overlap
        page1_ids = {c.id for c in page1}
        page2_ids = {c.id for c in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_list_by_shootout_eager_loads_user(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.list_by_shootout returns comments with user relationship loaded."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Test comment",
        )
        session.add(comment)
        await session.commit()

        comments = await repository.list_by_shootout(shootout.id)

        assert len(comments) == 1
        # Should be able to access user without lazy loading error
        assert comments[0].user.username == user.username


class TestShootoutCommentRepositoryDelete:
    """Tests for deleting comments."""

    @pytest.mark.asyncio
    async def test_delete_removes_comment_from_db(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.delete removes the comment from the database."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="To be deleted",
        )
        session.add(comment)
        await session.commit()
        comment_id = comment.id

        await repository.delete(comment_id)
        await session.commit()

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_comment(
        self,
        repository: ShootoutCommentRepository,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Repository.get_by_id returns the comment if found."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Find me",
        )
        session.add(comment)
        await session.flush()
        comment_id = comment.id
        owner_user_id = comment.user_id
        await session.commit()

        found = await repository.get_by_id(comment_id, owner_user_id)

        assert found is not None
        assert found.id == comment.id
        assert found.content == "Find me"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_missing(
        self,
        repository: ShootoutCommentRepository,
    ) -> None:
        """Repository.get_by_id returns None for non-existent comment."""
        found = await repository.get_by_id(uuid4(), uuid4())
        assert found is None
