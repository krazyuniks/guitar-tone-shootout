"""Integration tests for UserGearRepository implementation.

Tests for T13: UserGear Model and Repository
Tests the repository layer for managing user gear library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.base import new_id
from core.domain.entities.gear import Gear as GearEntity
from core.domain.entities.gear import UserGear as UserGearEntity
from core.domain.entities.user import User as UserEntity
from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.adapters.persistence.repositories.user_gear_repository import (
    SQLAlchemyUserGearRepository,
)
from webapp.adapters.persistence.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    Uses in-memory SQLite for fast, isolated testing.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Yield session
    async with session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def user_gear_repository(
    db_session: AsyncSession,
) -> SQLAlchemyUserGearRepository:
    """Create a UserGearRepository instance."""
    return SQLAlchemyUserGearRepository(db_session)


@pytest.fixture
def user_repository(db_session: AsyncSession) -> SQLAlchemyUserRepository:
    """Create a UserRepository instance."""
    return SQLAlchemyUserRepository(db_session)


@pytest.fixture
def gear_repository(db_session: AsyncSession) -> SQLAlchemyGearRepository:
    """Create a GearRepository instance."""
    return SQLAlchemyGearRepository(db_session)


@pytest.fixture
async def test_user(
    user_repository: SQLAlchemyUserRepository,
    db_session: AsyncSession,
) -> UserEntity:
    """Create a test user."""
    user = UserEntity(
        id=new_id(),
        username="test_user",
        email="test@example.com",
    )
    await user_repository.save(user)
    await db_session.commit()
    return user


@pytest.fixture
async def test_gear(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> GearEntity:
    """Create test gear."""
    gear = GearEntity(
        id=new_id(),
        name="Test Amp",
        gear_type=GearType.AMP,
        description="Test amplifier",
    )
    await gear_repository.save(gear)
    await db_session.commit()
    return gear


async def test_add_gear_to_library(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test adding gear to user's library."""
    user_gear = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )

    await user_gear_repository.add(user_gear)
    await db_session.commit()

    # Verify it was added
    retrieved = await user_gear_repository.get_by_user_and_gear(
        test_user.id, test_gear.id
    )

    assert retrieved is not None
    assert retrieved.user_id == test_user.id
    assert retrieved.gear_id == test_gear.id


async def test_remove_gear_from_library(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test removing gear from user's library."""
    # Add gear first
    user_gear = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    await user_gear_repository.add(user_gear)
    await db_session.commit()

    # Remove gear
    await user_gear_repository.remove(test_user.id, test_gear.id)
    await db_session.commit()

    # Verify it was removed
    retrieved = await user_gear_repository.get_by_user_and_gear(
        test_user.id, test_gear.id
    )
    assert retrieved is None


async def test_list_user_gear(
    user_gear_repository: SQLAlchemyUserGearRepository,
    gear_repository: SQLAlchemyGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test listing all gear in user's library."""
    # Create additional gear
    gear2 = GearEntity(
        id=new_id(),
        name="Test Pedal",
        gear_type=GearType.PEDAL,
    )
    await gear_repository.save(gear2)
    await db_session.commit()

    # Add both to user's library
    user_gear1 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    user_gear2 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=gear2.id,
    )

    await user_gear_repository.add(user_gear1)
    await user_gear_repository.add(user_gear2)
    await db_session.commit()

    # List user's gear
    user_gear_list = await user_gear_repository.list_by_user(test_user.id)

    assert len(user_gear_list) == 2
    gear_ids = {ug.gear_id for ug in user_gear_list}
    assert gear_ids == {test_gear.id, gear2.id}


async def test_list_user_gear_empty(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
) -> None:
    """Test listing gear for user with empty library."""
    user_gear_list = await user_gear_repository.list_by_user(test_user.id)
    assert user_gear_list == []


async def test_get_by_user_and_gear_not_found(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
) -> None:
    """Test getting user_gear that doesn't exist."""
    fake_gear_id = uuid4()
    retrieved = await user_gear_repository.get_by_user_and_gear(
        test_user.id, fake_gear_id
    )
    assert retrieved is None


async def test_add_duplicate_gear_fails(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test that adding the same gear twice raises an error."""
    # Add gear first time
    user_gear1 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    await user_gear_repository.add(user_gear1)
    await db_session.commit()

    # Try to add same gear again
    user_gear2 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    await user_gear_repository.add(user_gear2)

    # Should fail on commit due to unique constraint
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_list_user_gear_with_nickname(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test that nickname is preserved when listing user gear."""
    user_gear = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
        nickname="My Favourite Amp",
    )

    await user_gear_repository.add(user_gear)
    await db_session.commit()

    # List and verify nickname
    user_gear_list = await user_gear_repository.list_by_user(test_user.id)

    assert len(user_gear_list) == 1
    assert user_gear_list[0].nickname == "My Favourite Amp"


async def test_list_user_gear_with_notes_and_favourite(
    user_gear_repository: SQLAlchemyUserGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test that notes and is_favourite are preserved."""
    user_gear = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
        notes="Great for metal",
        is_favourite=True,
    )

    await user_gear_repository.add(user_gear)
    await db_session.commit()

    # List and verify
    user_gear_list = await user_gear_repository.list_by_user(test_user.id)

    assert len(user_gear_list) == 1
    assert user_gear_list[0].notes == "Great for metal"
    assert user_gear_list[0].is_favourite is True


async def test_list_user_gear_isolated_between_users(
    user_gear_repository: SQLAlchemyUserGearRepository,
    user_repository: SQLAlchemyUserRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test that each user's library is isolated."""
    # Create second user
    user2 = UserEntity(
        id=new_id(),
        username="user2",
        email="user2@example.com",
    )
    await user_repository.save(user2)
    await db_session.commit()

    # Add gear to first user's library
    user_gear1 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    await user_gear_repository.add(user_gear1)
    await db_session.commit()

    # User2's library should be empty
    user2_gear = await user_gear_repository.list_by_user(user2.id)
    assert user2_gear == []

    # User1's library should have one item
    user1_gear = await user_gear_repository.list_by_user(test_user.id)
    assert len(user1_gear) == 1


async def test_count_user_gear(
    user_gear_repository: SQLAlchemyUserGearRepository,
    gear_repository: SQLAlchemyGearRepository,
    test_user: UserEntity,
    test_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test counting items in user's library."""
    # Initially zero
    count = await user_gear_repository.count_by_user(test_user.id)
    assert count == 0

    # Add one gear
    user_gear1 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=test_gear.id,
    )
    await user_gear_repository.add(user_gear1)
    await db_session.commit()

    count = await user_gear_repository.count_by_user(test_user.id)
    assert count == 1

    # Add second gear
    gear2 = GearEntity(
        id=new_id(),
        name="Test Pedal",
        gear_type=GearType.PEDAL,
    )
    await gear_repository.save(gear2)
    await db_session.commit()

    user_gear2 = UserGearEntity(
        id=new_id(),
        user_id=test_user.id,
        gear_id=gear2.id,
    )
    await user_gear_repository.add(user_gear2)
    await db_session.commit()

    count = await user_gear_repository.count_by_user(test_user.id)
    assert count == 2
