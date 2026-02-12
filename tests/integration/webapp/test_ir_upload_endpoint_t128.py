"""Integration tests for IR upload endpoint (T128).

Tests POST /api/v1/irs/upload which creates Gear + GearModel
for community-contributed impulse response files.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.irs import router

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for IR upload tests."""
    user = User(
        id=uuid4(),
        username="iruser",
        email="iruser@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another user for ownership tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.integration
class TestIRUploadEndpoint:
    """Tests for POST /api/v1/irs/upload endpoint."""

    async def test_upload_creates_gear_returns_201(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Uploading an IR file returns 201 with created Gear + GearModel."""
        from fastapi import FastAPI

        ir_file = tmp_path / "my_cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("my_cab.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
        }
        data = {
            "name": "My Custom Cab",
            "description": "A great cabinet IR",
        }

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        json = response.json()
        assert json["name"] == "My Custom Cab"
        assert json["description"] == "A great cabinet IR"
        assert "id" in json

        # Verify Gear was created in database
        from sqlalchemy import select

        result = await db_session.execute(select(Gear).where(Gear.name == "My Custom Cab"))
        gear = result.scalar_one_or_none()
        assert gear is not None
        assert gear.gear_type.value == "ir"

    async def test_upload_creates_gear_model_with_file_path(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload creates a GearModel linked to the Gear with the IR file path."""
        from fastapi import FastAPI

        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("cab.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
        }
        data = {"name": "Linked Cab IR"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        # Verify GearModel was created and linked
        from sqlalchemy import select

        gear_result = await db_session.execute(select(Gear).where(Gear.name == "Linked Cab IR"))
        gear = gear_result.scalar_one()

        model_result = await db_session.execute(
            select(GearModel).where(GearModel.gear_id == gear.id)
        )
        gear_model = model_result.scalar_one()
        assert gear_model.file_path is not None

    async def test_upload_requires_authentication(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Upload endpoint requires CurrentUser authentication."""
        from fastapi import FastAPI

        from webapp.auth.dependencies import set_user_override

        # Clear user override to simulate unauthenticated request
        set_user_override(None)

        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("cab.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
        }
        data = {"name": "Unauth IR"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 401

    async def test_upload_rejects_invalid_format(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload returns 400 for non-WAV/IR file formats."""
        from fastapi import FastAPI

        text_file = tmp_path / "not_ir.txt"
        text_file.write_text("This is not an IR file")

        files = {
            "file": ("not_ir.txt", io.BytesIO(text_file.read_bytes()), "text/plain"),
        }
        data = {"name": "Bad Format IR"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 400
        assert "format" in response.json()["detail"].lower()

    async def test_upload_detects_duplicate_checksum(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Upload returns 400 when the same IR file is uploaded twice."""
        from fastapi import FastAPI

        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        app = FastAPI()
        app.include_router(router)

        # First upload
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            files1 = {
                "file": ("cab.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
            }
            response1 = await client.post(
                "/api/v1/irs/upload",
                files=files1,
                data={"name": "First IR"},
            )

        assert response1.status_code == 201

        # Second upload with same file content
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            files2 = {
                "file": ("cab_copy.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
            }
            response2 = await client.post(
                "/api/v1/irs/upload",
                files=files2,
                data={"name": "Duplicate IR"},
            )

        assert response2.status_code == 400
        assert "duplicate" in response2.json()["detail"].lower()

    async def test_upload_stores_file_safely(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Uploaded file is stored with a safe filename in the upload directory."""
        from fastapi import FastAPI

        ir_file = tmp_path / "my cab (special chars!).wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": (
                "my cab (special chars!).wav",
                io.BytesIO(ir_file.read_bytes()),
                "audio/wav",
            ),
        }
        data = {"name": "Safe Filename IR"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        # Verify saved file path doesn't contain unsafe chars
        from sqlalchemy import select

        gear_result = await db_session.execute(select(Gear).where(Gear.name == "Safe Filename IR"))
        gear = gear_result.scalar_one()

        model_result = await db_session.execute(
            select(GearModel).where(GearModel.gear_id == gear.id)
        )
        gear_model = model_result.scalar_one()
        # File should be saved with UUID-based or sanitised name
        assert gear_model.file_path is not None
        assert "(" not in gear_model.file_path
        assert "!" not in gear_model.file_path

    async def test_upload_defaults_gear_type_to_ir(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """When no gear_type is specified, it defaults to 'ir'."""
        from fastapi import FastAPI

        ir_file = tmp_path / "cab.wav"
        ir_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("cab.wav", io.BytesIO(ir_file.read_bytes()), "audio/wav"),
        }
        # No gear_type in data — should default
        data = {"name": "Default Type IR"}

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/irs/upload",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        from sqlalchemy import select

        result = await db_session.execute(select(Gear).where(Gear.name == "Default Type IR"))
        gear = result.scalar_one()
        assert gear.gear_type == GearType.IR
