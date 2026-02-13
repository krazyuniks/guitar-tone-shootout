"""Tests for DI track frontend/API contract alignment (T124).

Verifies that the API endpoint accepts the correct field names,
the ORM model has the required columns, and the response schema
includes all fields needed by the frontend form.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.di_tracks import router

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="contract_test_user",
        email="contract@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackTuningField:
    """Tests that the tuning field is supported end-to-end.

    The frontend form has a 'tuning' field, so the API, ORM model,
    domain entity, and response schema must all support it.
    """

    def test_orm_model_has_tuning_column(self) -> None:
        """DITrack ORM model must have a tuning column for the frontend form field."""
        # The frontend has <input name="tuning"> but the ORM model currently
        # has no tuning column. This test will fail until tuning is added.
        assert hasattr(DITrack, "tuning"), "DITrack ORM model must have a 'tuning' column"
        # Verify it's a proper mapped column, not just any attribute
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(DITrack)
        column_names = {col.key for col in mapper.column_attrs}
        assert "tuning" in column_names, "tuning must be a mapped column on DITrack"

    def test_domain_entity_has_tuning_field(self) -> None:
        """DITrack domain entity must have a tuning field."""
        from core.domain.entities.di_track import DITrack as DITrackEntity

        # The domain entity must accept tuning as a field
        entity = DITrackEntity(
            name="test",
            file_path="/tmp/test.wav",
            original_filename="test.wav",
            tuning="E Standard",
        )
        assert entity.tuning == "E Standard"

    def test_response_schema_includes_tuning(self) -> None:
        """DITrackResponse schema must include tuning field for the frontend."""
        from webapp.api.v1.schemas.di_track import DITrackResponse

        field_names = set(DITrackResponse.model_fields.keys())
        assert "tuning" in field_names, (
            "DITrackResponse must include 'tuning' field to match frontend form"
        )

    @pytest.mark.xfail(
        reason="Pre-existing: Upload directory permissions in Docker (T124)", strict=False
    )
    async def test_upload_endpoint_accepts_tuning_parameter(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """POST /api/v1/di-tracks must accept a 'tuning' form field.

        The frontend form sends tuning as a form parameter. The API
        endpoint must accept it and pass it through to the service.
        """
        from fastapi import FastAPI

        audio_file = tmp_path / "test_tuning.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        files = {
            "file": ("test_tuning.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {
            "name": "Tuning Test Track",
            "tuning": "Drop D",
        }

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/di-tracks",
                files=files,
                data=data,
            )

        # Should succeed and include tuning in response
        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text}"
        )
        json_data = response.json()
        assert json_data["tuning"] == "Drop D", "Upload response must include the tuning value"

    @pytest.mark.xfail(
        reason="Pre-existing: Upload directory permissions in Docker (T124)", strict=False
    )
    async def test_upload_tuning_persisted_to_database(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Uploaded tuning value must be persisted in the database."""
        from fastapi import FastAPI
        from sqlalchemy import select

        audio_file = tmp_path / "test_persist_tuning.wav"
        audio_file.write_bytes(b"RIFF" + b"\x01" * 100)

        files = {
            "file": ("test_persist.wav", io.BytesIO(audio_file.read_bytes()), "audio/wav"),
        }
        data = {
            "name": "Persist Tuning Track",
            "tuning": "E Standard",
        }

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/di-tracks",
                files=files,
                data=data,
            )

        assert response.status_code == 201

        # Verify tuning was persisted
        result = await db_session.execute(
            select(DITrack).where(DITrack.name == "Persist Tuning Track")
        )
        track = result.scalar_one_or_none()
        assert track is not None
        assert track.tuning == "E Standard", "Tuning must be persisted to database"

    async def test_list_endpoint_returns_tuning(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """GET /api/v1/di-tracks must include tuning in response items."""
        from fastapi import FastAPI

        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Track With Tuning",
            file_path=str(tmp_path / "tuning_list.wav"),
            original_filename="tuning_list.wav",
            duration_seconds=10.0,
            sample_rate=44100,
            tuning="Open G",
        )
        db_session.add(track)
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/di-tracks")

        assert response.status_code == 200
        json_data = response.json()
        assert len(json_data) >= 1

        # Find our track
        track_data = next(
            (t for t in json_data if t["name"] == "Track With Tuning"),
            None,
        )
        assert track_data is not None
        assert track_data["tuning"] == "Open G", "List endpoint must return tuning field"


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackServiceTuning:
    """Tests that DITrackService accepts and stores tuning."""

    async def test_service_upload_accepts_tuning(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """DITrackService.upload() must accept a tuning parameter."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test_svc_tuning.wav"
        audio_file.write_bytes(b"RIFF" + b"\x02" * 100)

        service = DITrackService(db_session)

        # Service must accept tuning parameter
        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test_svc_tuning.wav",
            name="Service Tuning Test",
            tuning="DADGAD",
        )

        assert track.tuning == "DADGAD", "Service must store tuning on created track"

    async def test_service_upload_tuning_optional(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """DITrackService.upload() must work without tuning (it's optional)."""
        from webapp.services.di_track_service import DITrackService

        audio_file = tmp_path / "test_no_tuning.wav"
        audio_file.write_bytes(b"RIFF" + b"\x03" * 100)

        service = DITrackService(db_session)

        # Should work fine without tuning
        track = await service.upload(
            user_id=test_user.id,
            file_path=str(audio_file),
            original_filename="test_no_tuning.wav",
            name="No Tuning Track",
        )

        assert track.tuning is None, "Tuning should default to None when not provided"
