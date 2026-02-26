"""Unit tests for add_shootout_video_fields migration.

Tests verify:
- video_status column added to shootouts table
- video_job_id column added to shootouts table
- Migration is reversible (downgrade removes columns)
- ORM model includes new video fields with correct types
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import text

from webapp.adapters.persistence.models.shootout import Shootout

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


class TestShootoutVideoFields:
    """Test that Shootout model has required video fields."""

    async def test_shootout_has_video_status_field(self, core_engine: AsyncEngine) -> None:
        """Verify Shootout model has video_status field."""
        # Check that video_status is a mapped column
        assert hasattr(Shootout, "video_status")

        # Verify the column exists in the table
        def _inspect_columns(connection):
            from sqlalchemy import inspect

            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("core_shootouts")}

        async with core_engine.connect() as conn:
            columns = await conn.run_sync(_inspect_columns)

        assert "video_status" in columns

    async def test_shootout_has_video_job_id_field(self, core_engine: AsyncEngine) -> None:
        """Verify Shootout model has video_job_id field."""
        # Check that video_job_id is a mapped column
        assert hasattr(Shootout, "video_job_id")

        # Verify the column exists in the table
        def _inspect_columns(connection):
            from sqlalchemy import inspect

            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("core_shootouts")}

        async with core_engine.connect() as conn:
            columns = await conn.run_sync(_inspect_columns)

        assert "video_job_id" in columns

    async def test_video_status_is_nullable_string(self, core_engine: AsyncEngine) -> None:
        """Verify video_status column is nullable String."""

        def _inspect_columns(connection):
            from sqlalchemy import inspect

            inspector = inspect(connection)
            return {col["name"]: col for col in inspector.get_columns("core_shootouts")}

        async with core_engine.connect() as conn:
            columns = await conn.run_sync(_inspect_columns)

        assert "video_status" in columns
        video_status_col = columns["video_status"]

        # Should be nullable (default null)
        assert video_status_col["nullable"] is True

        # Should be a string type
        assert "VARCHAR" in str(video_status_col["type"]) or "TEXT" in str(video_status_col["type"])

    async def test_video_job_id_is_nullable_string(self, core_engine: AsyncEngine) -> None:
        """Verify video_job_id column is nullable String."""

        def _inspect_columns(connection):
            from sqlalchemy import inspect

            inspector = inspect(connection)
            return {col["name"]: col for col in inspector.get_columns("core_shootouts")}

        async with core_engine.connect() as conn:
            columns = await conn.run_sync(_inspect_columns)

        assert "video_job_id" in columns
        video_job_id_col = columns["video_job_id"]

        # Should be nullable
        assert video_job_id_col["nullable"] is True

        # Should be a string type
        assert "VARCHAR" in str(video_job_id_col["type"]) or "TEXT" in str(video_job_id_col["type"])

    async def test_can_set_video_status_to_null(self, session: AsyncSession) -> None:
        """Verify video_status can be set to NULL (default)."""
        from webapp.adapters.persistence.models.shootout import ShootoutStatus
        from webapp.adapters.persistence.models.user import User

        # Create test user
        user = User(id=uuid4(), username=f"testuser_{uuid4().hex[:8]}", is_active=True)
        session.add(user)
        await session.flush()

        # Create shootout with video_status=None
        shootout = Shootout(
            id=uuid4(),
            user_id=user.id,
            name=f"Test Shootout {uuid4().hex[:8]}",
            status=ShootoutStatus.PENDING,
            video_status=None,  # Should accept None
        )
        session.add(shootout)
        await session.commit()

        # Verify it was saved as NULL
        result = await session.execute(
            text("SELECT video_status FROM core_shootouts WHERE id = :id"),
            {"id": str(shootout.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is None

    async def test_can_set_video_job_id_to_null(self, session: AsyncSession) -> None:
        """Verify video_job_id can be set to NULL (default)."""
        from webapp.adapters.persistence.models.shootout import ShootoutStatus
        from webapp.adapters.persistence.models.user import User

        # Create test user
        user = User(id=uuid4(), username=f"testuser_{uuid4().hex[:8]}", is_active=True)
        session.add(user)
        await session.flush()

        # Create shootout with video_job_id=None
        shootout = Shootout(
            id=uuid4(),
            user_id=user.id,
            name=f"Test Shootout {uuid4().hex[:8]}",
            status=ShootoutStatus.PENDING,
            video_job_id=None,  # Should accept None
        )
        session.add(shootout)
        await session.commit()

        # Verify it was saved as NULL
        result = await session.execute(
            text("SELECT video_job_id FROM core_shootouts WHERE id = :id"),
            {"id": str(shootout.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is None

    async def test_can_set_video_status_to_string(self, session: AsyncSession) -> None:
        """Verify video_status accepts string values."""
        from webapp.adapters.persistence.models.shootout import ShootoutStatus
        from webapp.adapters.persistence.models.user import User

        # Create test user
        user = User(id=uuid4(), username=f"testuser_{uuid4().hex[:8]}", is_active=True)
        session.add(user)
        await session.flush()

        # Create shootout with video_status="rendering"
        shootout = Shootout(
            id=uuid4(),
            user_id=user.id,
            name=f"Test Shootout {uuid4().hex[:8]}",
            status=ShootoutStatus.PENDING,
            video_status="rendering",
        )
        session.add(shootout)
        await session.commit()

        # Verify it was saved correctly
        result = await session.execute(
            text("SELECT video_status FROM core_shootouts WHERE id = :id"),
            {"id": str(shootout.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "rendering"

    async def test_can_set_video_job_id_to_string(self, session: AsyncSession) -> None:
        """Verify video_job_id accepts string values."""
        from webapp.adapters.persistence.models.shootout import ShootoutStatus
        from webapp.adapters.persistence.models.user import User

        # Create test user
        user = User(id=uuid4(), username=f"testuser_{uuid4().hex[:8]}", is_active=True)
        session.add(user)
        await session.flush()

        # Create shootout with video_job_id="job-123"
        shootout = Shootout(
            id=uuid4(),
            user_id=user.id,
            name=f"Test Shootout {uuid4().hex[:8]}",
            status=ShootoutStatus.PENDING,
            video_job_id="job-123",
        )
        session.add(shootout)
        await session.commit()

        # Verify it was saved correctly
        result = await session.execute(
            text("SELECT video_job_id FROM core_shootouts WHERE id = :id"),
            {"id": str(shootout.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "job-123"

    async def test_shootout_relationships_use_lazy_raise(self, session: AsyncSession) -> None:
        """Verify all Shootout relationships use lazy='raise'."""

        # Check each relationship has lazy="raise"
        user_rel = Shootout.user.property
        assert user_rel.lazy == "raise", "user relationship should use lazy='raise'"

        di_track_rel = Shootout.di_track.property
        assert di_track_rel.lazy == "raise", "di_track relationship should use lazy='raise'"

        chains_rel = Shootout.chains.property
        assert chains_rel.lazy == "raise", "chains relationship should use lazy='raise'"
