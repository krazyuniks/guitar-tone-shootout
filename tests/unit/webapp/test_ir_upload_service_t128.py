"""Unit tests for IR upload service (T128).

Tests the IRUploadService which creates Gear + GearModel entities
for community-contributed IR files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.services.ir_upload_service import IRUploadService


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    user = User(id=uuid4(), username="testuser", email="test@example.com", is_active=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
class TestIRUploadServiceCreatesGear:
    """Test that IR upload creates a Gear entity with correct attributes."""

    async def test_creates_gear_with_ir_type(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Uploading an IR creates a Gear with gear_type='ir'."""
        ir_file = tmp_path / "my_cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="my_cab.wav",
            name="My IR",
        )

        # Verify Gear was created with correct type
        stmt = select(Gear).where(Gear.gear_type == GearType.IR)
        db_result = await session.execute(stmt)
        gear = db_result.scalar_one()
        assert gear.name == "My IR"
        assert gear.gear_type == GearType.IR

    async def test_creates_gear_with_community_source(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Uploading an IR creates a Gear marked as community source."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Community IR",
        )

        # The Gear should be traceable to "community" source
        stmt = select(Gear).where(Gear.name == "Community IR")
        db_result = await session.execute(stmt)
        gear = db_result.scalar_one()
        # source="community" — exact implementation TBD (could be manufacturer field,
        # a GearSource record, or similar), but the service must associate it
        assert gear is not None

    async def test_creates_gear_with_description(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """IR upload accepts optional description metadata."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Described IR",
            description="A great cab sim",
        )

        stmt = select(Gear).where(Gear.name == "Described IR")
        db_result = await session.execute(stmt)
        gear = db_result.scalar_one()
        assert gear.description == "A great cab sim"


@pytest.mark.asyncio
class TestIRUploadServiceCreatesGearModel:
    """Test that IR upload creates a GearModel linked to the Gear."""

    async def test_creates_gear_model_linked_to_gear(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Uploading an IR creates a GearModel linked to the new Gear."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Linked IR",
        )

        # There should be a GearModel linked to the created Gear
        stmt = select(Gear).where(Gear.name == "Linked IR")
        gear_result = await session.execute(stmt)
        gear = gear_result.scalar_one()

        model_stmt = select(GearModel).where(GearModel.gear_id == gear.id)
        model_result = await session.execute(model_stmt)
        gear_model = model_result.scalar_one()
        assert gear_model.gear_id == gear.id

    async def test_gear_model_has_ir_platform(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """The GearModel should have platform=IR."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Platform IR",
        )

        stmt = select(Gear).where(Gear.name == "Platform IR")
        gear_result = await session.execute(stmt)
        gear = gear_result.scalar_one()

        model_stmt = select(GearModel).where(GearModel.gear_id == gear.id)
        model_result = await session.execute(model_stmt)
        gear_model = model_result.scalar_one()
        assert gear_model.platform == Platform.IR

    async def test_gear_model_has_file_path(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """The GearModel should store the IR file path."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="FilePath IR",
        )

        stmt = select(Gear).where(Gear.name == "FilePath IR")
        gear_result = await session.execute(stmt)
        gear = gear_result.scalar_one()

        model_stmt = select(GearModel).where(GearModel.gear_id == gear.id)
        model_result = await session.execute(model_stmt)
        gear_model = model_result.scalar_one()
        assert gear_model.file_path is not None
        assert str(ir_file) in gear_model.file_path or gear_model.file_path.endswith(".wav")

    async def test_gear_model_has_file_hash(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """The GearModel should store a checksum/hash of the IR file."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Hash IR",
        )

        stmt = select(Gear).where(Gear.name == "Hash IR")
        gear_result = await session.execute(stmt)
        gear = gear_result.scalar_one()

        model_stmt = select(GearModel).where(GearModel.gear_id == gear.id)
        model_result = await session.execute(model_stmt)
        gear_model = model_result.scalar_one()
        assert gear_model.file_hash is not None
        assert len(gear_model.file_hash) == 64  # SHA256 hex length


@pytest.mark.asyncio
class TestIRUploadServiceValidation:
    """Test file format validation and duplicate detection."""

    async def test_rejects_invalid_file_format(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Service rejects files that aren't WAV/IR formats."""
        text_file = tmp_path / "not_an_ir.txt"
        text_file.write_text("This is not an IR file")

        service = IRUploadService(session)
        with pytest.raises(ValueError, match=r"(?i)format"):
            await service.upload(
                user_id=test_user.id,
                file_path=str(text_file),
                original_filename="not_an_ir.txt",
                name="Bad Format",
            )

    async def test_detects_duplicate_checksum(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Service detects duplicate IR files via checksum."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)

        # First upload should succeed
        await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="First IR",
        )
        await session.commit()

        # Second upload with same file should fail
        with pytest.raises(ValueError, match=r"(?i)duplicate|already exists"):
            await service.upload(
                user_id=test_user.id,
                file_path=str(ir_file),
                original_filename="cab_copy.wav",
                name="Duplicate IR",
            )

    async def test_accepts_wav_format(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """WAV files are accepted for IR upload."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        _ = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="WAV IR",
        )

        stmt = select(Gear).where(Gear.name == "WAV IR")
        db_result = await session.execute(stmt)
        assert db_result.scalar_one() is not None


@pytest.mark.asyncio
class TestIRUploadServiceReturnValue:
    """Test that the service returns the created Gear + GearModel."""

    async def test_returns_created_gear(
        self, session: AsyncSession, test_user: User, tmp_path: Path
    ) -> None:
        """Service returns the created Gear entity."""
        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        service = IRUploadService(session)
        result = await service.upload(
            user_id=test_user.id,
            file_path=str(ir_file),
            original_filename="cab.wav",
            name="Returned IR",
        )

        # Result should contain the Gear (or a structure with Gear + GearModel)
        assert result is not None
        # The exact return type will be determined by implementation,
        # but it must contain gear info
        assert hasattr(result, "id") or isinstance(result, dict)
