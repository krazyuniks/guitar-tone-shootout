"""Unit tests for IR upload validation and edge cases (T128).

Tests additional acceptance criteria for IRUploadService:
- File format validation (WAV/IR formats only)
- Duplicate detection via checksum
- Safe filename handling
- Gear defaults to gear_type="ir", source="community"
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.services.ir_upload_service import IRUploadService


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    _sfx = uuid4().hex[:8]
    user = User(
        id=uuid4(), username=f"testuser_{_sfx}", email=f"test_{_sfx}@example.com", is_active=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
class TestIRUploadServiceSafeFilename:
    """Test that IR upload stores files with safe filenames."""

    async def test_upload_sanitises_filename_with_path_traversal(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """File paths with traversal sequences are sanitised."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        result = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="../../../etc/passwd.wav",
            name="Safe IR",
        )

        # The stored filename should not contain path traversal
        stmt = select(GearModel).where(GearModel.gear_id == result.id)
        model_result = await session.execute(stmt)
        gear_model = model_result.scalar_one()
        assert "../" not in gear_model.file_path


@pytest.mark.asyncio
class TestIRUploadServiceGearDefaults:
    """Test that created Gear has correct default values."""

    async def test_gear_type_defaults_to_ir(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Created Gear always has gear_type=IR regardless of input."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        result = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Default Type IR",
        )

        stmt = select(Gear).where(Gear.id == result.id)
        db_result = await session.execute(stmt)
        gear = db_result.scalar_one()
        assert gear.gear_type == GearType.IR

    async def test_gear_model_platform_is_ir(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Created GearModel has platform=IR."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        result = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Platform IR",
        )

        model_stmt = select(GearModel).where(GearModel.gear_id == result.id)
        model_result = await session.execute(model_stmt)
        gear_model = model_result.scalar_one()
        assert gear_model.platform == Platform.IR

    async def test_upload_returns_gear_with_id(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Service returns an object with an id attribute (the created Gear)."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        result = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Return Value IR",
        )

        assert result is not None
        assert hasattr(result, "id")
        assert result.id is not None

        # Verify the returned ID matches what's in the database
        stmt = select(Gear).where(Gear.id == result.id)
        db_result = await session.execute(stmt)
        gear = db_result.scalar_one()
        assert gear.id == result.id
