"""Unit tests for UserGear ORM model.

Tests for T13: UserGear Model and Repository
Tests the SQLAlchemy model for user gear library.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import joinedload

from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestUserGearModel:
    """Tests for UserGear ORM model."""

    async def test_user_gear_creation_with_required_fields(self, session: AsyncSession) -> None:
        """Test creating UserGear with only required fields (user_id, gear_model_id)."""
        # Create user, gear, and gear model first
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Create user gear link
        user_gear = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear)
        await session.commit()

        # Verify it was created
        result = await session.execute(select(UserGear).where(UserGear.user_id == user.id))
        saved = result.scalar_one()

        assert saved.id is not None
        assert saved.user_id == user.id
        assert saved.gear_model_id == gear_model.id
        assert saved.nickname is None
        assert saved.notes is None
        assert saved.is_favourite is False
        assert saved.created_at is not None
        assert saved.updated_at is not None

    async def test_user_gear_unique_constraint_prevents_duplicate(
        self, session: AsyncSession
    ) -> None:
        """Test that a user cannot add the same gear model twice (unique constraint)."""
        # Create user, gear, and gear model
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Add gear model to library
        user_gear1 = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear1)
        await session.commit()

        # Try to add same gear model again - should fail with IntegrityError
        user_gear2 = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear2)

        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_user_gear_allows_different_users_same_gear(self, session: AsyncSession) -> None:
        """Test that different users can add the same gear model to their library."""
        # Create two users, one gear, and one gear model
        user1 = User(username="user1", email="user1@example.com")
        user2 = User(username="user2", email="user2@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add_all([user1, user2, gear])
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Both users add the same gear model
        user_gear1 = UserGear(user_id=user1.id, gear_model_id=gear_model.id)
        user_gear2 = UserGear(user_id=user2.id, gear_model_id=gear_model.id)
        session.add_all([user_gear1, user_gear2])
        await session.commit()

        # Verify both were created
        result = await session.execute(select(UserGear))
        all_user_gear = result.scalars().all()

        assert len(all_user_gear) == 2
        user_ids = {ug.user_id for ug in all_user_gear}
        assert user_ids == {user1.id, user2.id}

    async def test_user_gear_with_optional_fields(self, session: AsyncSession) -> None:
        """Test creating UserGear with nickname, notes, and is_favourite."""
        # Create user, gear, and gear model
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Mesa Boogie", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Create with optional fields
        user_gear = UserGear(
            user_id=user.id,
            gear_model_id=gear_model.id,
            nickname="My Favourite Amp",
            notes="Great for metal",
            is_favourite=True,
        )
        session.add(user_gear)
        await session.commit()

        # Verify optional fields
        result = await session.execute(select(UserGear).where(UserGear.user_id == user.id))
        saved = result.scalar_one()

        assert saved.nickname == "My Favourite Amp"
        assert saved.notes == "Great for metal"
        assert saved.is_favourite is True

    async def test_user_gear_foreign_key_to_user(self, session: AsyncSession) -> None:
        """Test that user_id references the users table."""
        # Create gear and gear model but no user
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Try to create user_gear with non-existent user_id
        fake_user_id = uuid4()
        user_gear = UserGear(user_id=fake_user_id, gear_model_id=gear_model.id)
        session.add(user_gear)

        # Should fail with IntegrityError (foreign key violation)
        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_user_gear_foreign_key_to_gear(self, session: AsyncSession) -> None:
        """Test that gear_model_id references the gear_models table."""
        # Create user but no gear model
        user = User(username="test_user", email="test@example.com")
        session.add(user)
        await session.flush()

        # Try to create user_gear with non-existent gear_model_id
        fake_gear_model_id = uuid4()
        user_gear = UserGear(user_id=user.id, gear_model_id=fake_gear_model_id)
        session.add(user_gear)

        # Should fail with IntegrityError (foreign key violation)
        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_user_gear_cascade_delete_on_user(self, session: AsyncSession) -> None:
        """Test that deleting a user deletes their user_gear entries."""
        # Create user, gear, and gear model
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Add gear model to user's library
        user_gear = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear)
        await session.commit()

        # Delete the user
        await session.delete(user)
        await session.commit()

        # Verify user_gear was also deleted (cascade)
        result = await session.execute(select(UserGear))
        remaining = result.scalars().all()
        assert len(remaining) == 0

    async def test_user_gear_has_relationship_to_user(self, session: AsyncSession) -> None:
        """Test that UserGear has a relationship to User model."""
        # Create user, gear, and gear model
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Create user gear
        user_gear = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear)
        await session.commit()

        # Fetch user_gear and access user via relationship
        result = await session.execute(
            select(UserGear).where(UserGear.user_id == user.id).options(joinedload(UserGear.user))
        )
        saved = result.unique().scalar_one()

        # Access user via relationship (eager-loaded via joinedload)
        assert saved.user is not None
        assert saved.user.username == "test_user"

    async def test_user_gear_has_relationship_to_gear(self, session: AsyncSession) -> None:
        """Test that UserGear has a relationship to GearModel."""
        # Create user, gear, and gear model
        user = User(username="test_user", email="test@example.com")
        gear = Gear(name="Test Amp", gear_type=GearType.AMP, platform=Platform.NAM)
        session.add(user)
        session.add(gear)
        await session.flush()

        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        session.add(gear_model)
        await session.flush()

        # Create user gear
        user_gear = UserGear(user_id=user.id, gear_model_id=gear_model.id)
        session.add(user_gear)
        await session.commit()

        # Fetch user_gear and access gear_model via relationship
        result = await session.execute(
            select(UserGear)
            .where(UserGear.user_id == user.id)
            .options(joinedload(UserGear.gear_model))
        )
        saved = result.unique().scalar_one()

        # Access gear_model via relationship (eager-loaded via joinedload)
        assert saved.gear_model is not None
        assert saved.gear_model.platform == Platform.NAM
        assert saved.gear_model.size == ModelSize.STANDARD
