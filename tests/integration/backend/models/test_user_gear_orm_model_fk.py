"""Integration tests for UserGear ORM model FK to gear_models table."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.mark.integration
class TestUserGearORMModelFK:
    """Test UserGear ORM model has gear_model_id FK pointing to gear_models.id."""

    async def test_user_gear_has_gear_model_id_column(self, session: AsyncSession) -> None:
        """UserGear table should have gear_model_id column."""
        # Query column metadata
        result = await session.execute(text("PRAGMA table_info(user_gear)"))
        columns = {row[1]: row for row in result.fetchall()}

        assert "gear_model_id" in columns

    async def test_user_gear_does_not_have_gear_id_column(self, session: AsyncSession) -> None:
        """UserGear table should NOT have gear_id column."""
        result = await session.execute(text("PRAGMA table_info(user_gear)"))
        columns = {row[1]: row for row in result.fetchall()}

        assert "gear_id" not in columns

    async def test_user_gear_fk_points_to_gear_models_table(self, session: AsyncSession) -> None:
        """gear_model_id foreign key should point to gear_models.id."""
        # Get foreign key constraints
        result = await session.execute(text("PRAGMA foreign_key_list(user_gear)"))
        foreign_keys = result.fetchall()

        # Find the gear_model_id FK
        gear_model_fks = [
            fk
            for fk in foreign_keys
            if fk[3] == "gear_model_id"  # 'from' column
        ]

        assert len(gear_model_fks) == 1
        fk = gear_model_fks[0]
        assert fk[2] == "gear_models"  # 'table' field
        assert fk[4] == "id"  # 'to' column

    async def test_user_gear_unique_constraint_uses_gear_model_id(
        self, session: AsyncSession
    ) -> None:
        """Unique constraint should be on (user_id, gear_model_id)."""
        # Get index info
        result = await session.execute(text("PRAGMA index_list(user_gear)"))
        indexes = result.fetchall()

        # Find unique constraint index
        unique_indexes = [idx for idx in indexes if idx[2] == 1]  # unique=1

        # Check index columns
        found_correct_constraint = False
        for idx in unique_indexes:
            idx_name = idx[1]
            result = await session.execute(text(f"PRAGMA index_info({idx_name})"))
            columns = [row[2] for row in result.fetchall()]

            if "user_id" in columns and "gear_model_id" in columns:
                found_correct_constraint = True
                break

        assert found_correct_constraint, "Expected unique constraint on (user_id, gear_model_id)"

    async def test_user_gear_creation_with_gear_model_id(self, session: AsyncSession) -> None:
        """Should be able to create UserGear with gear_model_id FK."""
        # Create prerequisites
        user = User(id=uuid4(), username="test_user", email="test@example.com")
        gear = Gear(
            id=uuid4(),
            name="Test Amp",
            slug="test-amp",
            gear_type="amp",
            platform="nam",
        )
        gear_model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform="nam",
            size="standard",
        )

        session.add_all([user, gear, gear_model])
        await session.flush()

        # Create UserGear with gear_model_id
        user_gear = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )

        session.add(user_gear)
        await session.commit()

        # Verify
        result = await session.execute(select(UserGear).where(UserGear.id == user_gear.id))
        saved = result.scalar_one()
        assert saved.gear_model_id == gear_model.id

    async def test_user_gear_prevents_duplicate_user_model_pairs(
        self, session: AsyncSession
    ) -> None:
        """Unique constraint should prevent duplicate (user_id, gear_model_id) pairs."""
        # Create prerequisites
        user = User(id=uuid4(), username="test_user", email="test@example.com")
        gear = Gear(
            id=uuid4(),
            name="Test Amp",
            slug="test-amp",
            gear_type="amp",
            platform="nam",
        )
        gear_model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform="nam",
            size="standard",
        )

        session.add_all([user, gear, gear_model])
        await session.flush()

        # Create first UserGear
        user_gear1 = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )
        session.add(user_gear1)
        await session.commit()

        # Try to create duplicate
        user_gear2 = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )
        session.add(user_gear2)

        with pytest.raises(Exception):  # IntegrityError for unique constraint violation
            await session.commit()
