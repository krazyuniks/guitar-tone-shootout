"""Unit tests for ShootoutCommentService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.shootout import (
    DITrack,
    Shootout,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.user import User
from webapp.services.shootout_comment_service import ShootoutCommentService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    """Create a second test user."""
    user = User(username="otheruser", email="other@example.com")
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
def service(session: AsyncSession) -> ShootoutCommentService:
    """Create a ShootoutCommentService instance."""
    return ShootoutCommentService(session)


class TestShootoutCommentServiceCreate:
    """Tests for ShootoutCommentService.create."""

    @pytest.mark.asyncio
    async def test_create_comment_returns_comment_with_user(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create returns a comment with user info populated."""
        comment = await service.create(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Nice shootout!",
        )

        assert comment.content == "Nice shootout!"
        assert comment.shootout_id == shootout.id
        assert comment.user_id == user.id
        assert comment.id is not None

    @pytest.mark.asyncio
    async def test_create_comment_persists_to_database(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create persists the comment to the database."""
        comment = await service.create(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Persisted comment",
        )

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment.id)
        )
        saved = result.scalar_one()
        assert saved.content == "Persisted comment"

    @pytest.mark.asyncio
    async def test_create_comment_validates_empty_content(
        self,
        service: ShootoutCommentService,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create raises ValueError for empty content."""
        with pytest.raises(ValueError, match="[Cc]ontent"):
            await service.create(
                shootout_id=shootout.id,
                user_id=user.id,
                content="",
            )

    @pytest.mark.asyncio
    async def test_create_comment_validates_whitespace_only_content(
        self,
        service: ShootoutCommentService,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create raises ValueError for whitespace-only content."""
        with pytest.raises(ValueError, match="[Cc]ontent"):
            await service.create(
                shootout_id=shootout.id,
                user_id=user.id,
                content="   ",
            )

    @pytest.mark.asyncio
    async def test_create_comment_validates_max_length(
        self,
        service: ShootoutCommentService,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create raises ValueError for content over 2000 chars."""
        long_content = "x" * 2001
        with pytest.raises(ValueError, match="2000"):
            await service.create(
                shootout_id=shootout.id,
                user_id=user.id,
                content=long_content,
            )

    @pytest.mark.asyncio
    async def test_create_comment_accepts_max_length_content(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.create accepts content of exactly 2000 chars."""
        content = "x" * 2000
        comment = await service.create(
            shootout_id=shootout.id,
            user_id=user.id,
            content=content,
        )
        assert len(comment.content) == 2000

    @pytest.mark.asyncio
    async def test_create_comment_raises_for_nonexistent_shootout(
        self,
        service: ShootoutCommentService,
        user: User,
    ) -> None:
        """Service.create raises ValueError when shootout doesn't exist."""
        with pytest.raises(ValueError, match="[Ss]hootout"):
            await service.create(
                shootout_id=uuid4(),
                user_id=user.id,
                content="Comment on missing shootout",
            )


class TestShootoutCommentServiceListByShootout:
    """Tests for ShootoutCommentService.list_by_shootout."""

    @pytest.mark.asyncio
    async def test_list_by_shootout_returns_comments(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.list_by_shootout returns comments for the shootout."""
        # Create comments directly in DB
        comment1 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Comment 1",
        )
        comment2 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Comment 2",
        )
        session.add_all([comment1, comment2])
        await session.commit()

        comments = await service.list_by_shootout(shootout.id)

        assert len(comments) == 2

    @pytest.mark.asyncio
    async def test_list_by_shootout_returns_newest_first(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.list_by_shootout returns comments in newest-first order."""
        comment1 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Older",
        )
        comment2 = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Newer",
        )
        session.add_all([comment1, comment2])
        await session.commit()

        comments = await service.list_by_shootout(shootout.id)

        assert comments[0].content == "Newer"
        assert comments[1].content == "Older"

    @pytest.mark.asyncio
    async def test_list_by_shootout_raises_for_nonexistent_shootout(
        self,
        service: ShootoutCommentService,
    ) -> None:
        """Service.list_by_shootout raises ValueError when shootout doesn't exist."""
        with pytest.raises(ValueError, match="[Ss]hootout"):
            await service.list_by_shootout(uuid4())


class TestShootoutCommentServiceDelete:
    """Tests for ShootoutCommentService.delete."""

    @pytest.mark.asyncio
    async def test_delete_removes_comment(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        shootout: Shootout,
    ) -> None:
        """Service.delete removes the comment from the database."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Delete me",
        )
        session.add(comment)
        await session.commit()

        await service.delete(comment_id=comment.id, user_id=user.id)

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_raises_for_nonexistent_comment(
        self,
        service: ShootoutCommentService,
        user: User,
    ) -> None:
        """Service.delete raises ValueError for non-existent comment."""
        with pytest.raises(ValueError, match="[Cc]omment"):
            await service.delete(comment_id=uuid4(), user_id=user.id)

    @pytest.mark.asyncio
    async def test_delete_raises_when_user_is_not_author(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        other_user: User,
        shootout: Shootout,
    ) -> None:
        """Service.delete raises PermissionError when user is not the comment author."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Not yours to delete",
        )
        session.add(comment)
        await session.commit()

        with pytest.raises(PermissionError):
            await service.delete(comment_id=comment.id, user_id=other_user.id)

    @pytest.mark.asyncio
    async def test_delete_does_not_remove_other_users_comment(
        self,
        service: ShootoutCommentService,
        session: AsyncSession,
        user: User,
        other_user: User,
        shootout: Shootout,
    ) -> None:
        """Service.delete does not delete the comment when not the author."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Still here",
        )
        session.add(comment)
        await session.commit()
        comment_id = comment.id

        with pytest.raises(PermissionError):
            await service.delete(comment_id=comment_id, user_id=other_user.id)

        # Verify comment still exists
        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment_id)
        )
        assert result.scalar_one_or_none() is not None
