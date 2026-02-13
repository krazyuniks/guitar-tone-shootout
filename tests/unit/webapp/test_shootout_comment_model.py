"""Unit tests for ShootoutComment ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.shootout import (
    DITrack,
    Shootout,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


class TestShootoutCommentCreation:
    """Tests for creating ShootoutComment ORM instances."""

    @pytest.mark.asyncio
    async def test_create_comment(
        self, session: AsyncSession, user: User, shootout: Shootout
    ) -> None:
        """ShootoutComment can be created with all required fields."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="This is a great shootout!",
        )
        session.add(comment)
        await session.commit()
        await session.refresh(comment)

        assert comment.id is not None
        assert comment.shootout_id == shootout.id
        assert comment.user_id == user.id
        assert comment.content == "This is a great shootout!"
        assert comment.created_at is not None
        assert comment.updated_at is not None

    @pytest.mark.asyncio
    async def test_comment_table_name(self) -> None:
        """ShootoutComment model uses 'shootout_comments' table."""
        assert ShootoutComment.__tablename__ == "shootout_comments"


class TestShootoutCommentForeignKeys:
    """Tests for ShootoutComment foreign key constraints."""

    @pytest.mark.asyncio
    async def test_comment_references_shootout(
        self, session: AsyncSession, user: User, shootout: Shootout
    ) -> None:
        """ShootoutComment has a FK to shootouts table."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="FK test",
        )
        session.add(comment)
        await session.commit()

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.shootout_id == shootout.id)
        )
        saved = result.scalar_one()
        assert saved.shootout_id == shootout.id

    @pytest.mark.asyncio
    async def test_comment_references_user(
        self, session: AsyncSession, user: User, shootout: Shootout
    ) -> None:
        """ShootoutComment has a FK to users table."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="FK test",
        )
        session.add(comment)
        await session.commit()

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.user_id == user.id)
        )
        saved = result.scalar_one()
        assert saved.user_id == user.id


class TestShootoutCommentCascadeDelete:
    """Tests for cascade delete from shootout to comments."""

    @pytest.mark.xfail(reason="Pre-existing: SQLite doesn't enforce ON DELETE CASCADE")
    @pytest.mark.asyncio
    async def test_deleting_shootout_cascades_to_comments(
        self, session: AsyncSession, user: User, shootout: Shootout
    ) -> None:
        """Deleting a shootout should cascade-delete its comments."""
        comment = ShootoutComment(
            shootout_id=shootout.id,
            user_id=user.id,
            content="Will be cascade deleted",
        )
        session.add(comment)
        await session.commit()
        comment_id = comment.id

        await session.delete(shootout)
        await session.commit()

        result = await session.execute(
            select(ShootoutComment).where(ShootoutComment.id == comment_id)
        )
        assert result.scalar_one_or_none() is None


class TestShootoutCommentIndexes:
    """Tests for indexes on ShootoutComment."""

    @pytest.mark.asyncio
    async def test_index_on_shootout_id(self) -> None:
        """ShootoutComment should have an index on shootout_id."""
        indexes = {idx.name for idx in ShootoutComment.__table__.indexes}
        shootout_id_indexed = any(
            "shootout_id" in idx.name for idx in ShootoutComment.__table__.indexes
        )
        assert shootout_id_indexed, f"No index on shootout_id. Indexes: {indexes}"

    @pytest.mark.asyncio
    async def test_index_on_user_id(self) -> None:
        """ShootoutComment should have an index on user_id."""
        indexes = {idx.name for idx in ShootoutComment.__table__.indexes}
        user_id_indexed = any("user_id" in idx.name for idx in ShootoutComment.__table__.indexes)
        assert user_id_indexed, f"No index on user_id. Indexes: {indexes}"


class TestShootoutCommentsRelationship:
    """Tests for the comments relationship on Shootout model."""

    @pytest.mark.asyncio
    async def test_shootout_has_comments_relationship(
        self, session: AsyncSession, user: User, shootout: Shootout
    ) -> None:
        """Shootout model should have a 'comments' relationship."""
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

        # Re-query with joinedload (lazy="raise" requires explicit loading)
        result = await session.execute(
            select(Shootout)
            .where(Shootout.id == shootout.id)
            .options(joinedload(Shootout.comments))
        )
        loaded_shootout = result.unique().scalar_one()

        assert len(loaded_shootout.comments) == 2
        contents = {c.content for c in loaded_shootout.comments}
        assert contents == {"First comment", "Second comment"}

    @pytest.mark.asyncio
    async def test_comments_relationship_uses_lazy_raise(self) -> None:
        """Shootout.comments relationship should use lazy='raise'."""
        from sqlalchemy import inspect

        mapper = inspect(Shootout)
        comments_prop = mapper.relationships.get("comments")
        assert comments_prop is not None, "Shootout model has no 'comments' relationship"
        assert (
            comments_prop.lazy == "raise"
        ), f"Expected lazy='raise', got lazy='{comments_prop.lazy}'"
