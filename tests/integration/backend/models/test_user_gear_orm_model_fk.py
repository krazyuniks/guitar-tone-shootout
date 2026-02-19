"""Integration tests for UserGear ORM model FK to gear_models table."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
class TestUserGearORMModelFK:
    """Test UserGear ORM model has gear_model_id FK pointing to gear_models.id."""

    async def test_user_gear_has_gear_model_id_column(self, db_session: AsyncSession) -> None:
        """UserGear table should have gear_model_id column."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'user_gear'"
            )
        )
        columns = {row[0] for row in result.fetchall()}

        assert "gear_model_id" in columns

    async def test_user_gear_does_not_have_gear_id_column(self, db_session: AsyncSession) -> None:
        """UserGear table should NOT have gear_id column."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'user_gear'"
            )
        )
        columns = {row[0] for row in result.fetchall()}

        assert "gear_id" not in columns

    async def test_user_gear_fk_points_to_gear_models_table(self, db_session: AsyncSession) -> None:
        """gear_model_id foreign key should point to gear_models.id."""
        result = await db_session.execute(
            text("""
            SELECT
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'user_gear'
                AND kcu.column_name = 'gear_model_id'
        """)
        )
        fks = result.fetchall()

        assert len(fks) == 1
        fk = fks[0]
        assert fk[1] == "gear_models"  # to_table
        assert fk[2] == "id"  # to_column

    async def test_user_gear_unique_constraint_uses_gear_model_id(
        self, db_session: AsyncSession
    ) -> None:
        """Unique constraint should be on (user_id, gear_model_id)."""
        result = await db_session.execute(
            text("""
            SELECT
                indexdef
            FROM pg_indexes
            WHERE tablename = 'user_gear'
        """)
        )
        indexes = result.fetchall()

        # Find unique index that has both user_id and gear_model_id
        found_correct_constraint = False
        for idx in indexes:
            indexdef = idx[0]
            if (
                "UNIQUE" in indexdef.upper()
                and "user_id" in indexdef
                and "gear_model_id" in indexdef
            ):
                found_correct_constraint = True
                break

        assert found_correct_constraint, "Expected unique constraint on (user_id, gear_model_id)"

    async def test_user_gear_creation_with_gear_model_id(self, db_session: AsyncSession) -> None:
        """Should be able to create UserGear with gear_model_id FK."""
        suffix = uuid4().hex[:8]
        # Create prerequisites
        user = User(id=uuid4(), username=f"test_user_{suffix}", email=f"test_{suffix}@example.com")
        gear = Gear(
            id=uuid4(),
            name=f"Test Amp {suffix}",
            slug=f"test-amp-{suffix}",
            gear_type="amp",
            platform="nam",
        )
        gear_model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform="nam",
            size="standard",
        )

        db_session.add_all([user, gear, gear_model])
        await db_session.flush()

        # Create UserGear with gear_model_id
        user_gear = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )

        db_session.add(user_gear)
        await db_session.commit()

        # Verify
        result = await db_session.execute(select(UserGear).where(UserGear.id == user_gear.id))
        saved = result.scalar_one()
        assert saved.gear_model_id == gear_model.id

    async def test_user_gear_prevents_duplicate_user_model_pairs(
        self, db_session: AsyncSession
    ) -> None:
        """Unique constraint should prevent duplicate (user_id, gear_model_id) pairs."""
        suffix = uuid4().hex[:8]
        # Create prerequisites
        user = User(id=uuid4(), username=f"test_user_{suffix}", email=f"test_{suffix}@example.com")
        gear = Gear(
            id=uuid4(),
            name=f"Test Amp {suffix}",
            slug=f"test-amp-{suffix}",
            gear_type="amp",
            platform="nam",
        )
        gear_model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform="nam",
            size="standard",
        )

        db_session.add_all([user, gear, gear_model])
        await db_session.flush()

        # Create first UserGear
        user_gear1 = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )
        db_session.add(user_gear1)
        await db_session.commit()

        # Try to create duplicate
        user_gear2 = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear_model.id,
        )
        db_session.add(user_gear2)

        with pytest.raises(Exception):  # IntegrityError for unique constraint violation
            await db_session.commit()
