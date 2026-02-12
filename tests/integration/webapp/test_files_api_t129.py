"""Integration tests for file serving API endpoint (T129).

Tests GET /api/v1/files/{signature} which streams files
using HMAC-signed URLs with expiration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for file serving tests."""
    user = User(
        id=uuid4(),
        username="fileuser",
        email="fileuser@example.com",
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
        username="otherfileuser",
        email="otherfile@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def _create_app():
    """Create a minimal FastAPI app with the files router."""
    from fastapi import FastAPI

    from webapp.api.v1.files import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesEndpointStreaming:
    """Tests for GET /api/v1/files/{signature} file streaming."""

    async def test_valid_signature_streams_file(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """A valid signature returns the file content with 200."""
        from webapp.services.asset_service import AssetService

        # Create a test file in the upload directory
        upload_dir = tmp_path
        file_rel = "di-tracks/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_content = b"RIFF" + b"\x00" * 100
        file_abs.write_bytes(file_content)

        # Generate a signed URL
        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 200
        assert response.content == file_content

    async def test_correct_content_type_for_wav(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """WAV files are served with audio/wav content type."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        file_rel = "di-tracks/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_abs.write_bytes(b"RIFF" + b"\x00" * 100)

        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 200
        assert "audio" in response.headers.get("content-type", "")


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesEndpointSignatureValidation:
    """Tests for signature validation in the files endpoint."""

    async def test_invalid_signature_returns_404(
        self,
        db_session: AsyncSession,
    ) -> None:
        """An invalid/tampered signature returns 404 (not 403)."""
        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/files/invalid-signature-here")

        # Must return 404, not 403 — no existence leaking
        assert response.status_code == 404

    async def test_expired_signature_returns_404(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """An expired signature returns 404."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )

        # Generate already-expired signature
        signature = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=test_user.id,
            expires_in=-1,  # Already expired
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 404

    async def test_tampered_signature_returns_404(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """A tampered signature returns 404."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=test_user.id,
            expires_in=3600,
        )

        # Tamper
        tampered = signature[:-4] + "XXXX"

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{tampered}")

        assert response.status_code == 404

    async def test_empty_signature_returns_404(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Empty signature path returns 404 or 405."""
        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # With empty path segment, FastAPI may return 404 or 405
            response = await client.get("/api/v1/files/")

        assert response.status_code in (404, 405, 422)


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesEndpointOwnership:
    """Tests for file ownership validation."""

    async def test_missing_file_returns_404(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """A valid signature for a file that doesn't exist on disk returns 404."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )

        # Sign a path that doesn't exist on disk
        signature = service.generate_signed_url(
            file_path="di-tracks/nonexistent.wav",
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesEndpointRangeHeaders:
    """Tests for Range header support (streaming large audio files)."""

    async def test_supports_range_header(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """The endpoint supports Range headers for partial content."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        file_rel = "di-tracks/large_track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        # Write 1KB of data
        file_content = b"RIFF" + b"\x00" * 1020
        file_abs.write_bytes(file_content)

        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/files/{signature}",
                headers={"Range": "bytes=0-99"},
            )

        # 206 Partial Content for range requests
        assert response.status_code == 206
        assert len(response.content) == 100
        assert "content-range" in response.headers

    async def test_full_request_without_range(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Without Range header, full file is returned with 200."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path
        file_rel = "di-tracks/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_content = b"RIFF" + b"\x00" * 100
        file_abs.write_bytes(file_content)

        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 200
        assert response.content == file_content


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesEndpointPathTraversal:
    """Tests that the endpoint rejects path traversal in file serving."""

    async def test_symlink_outside_upload_dir_returns_404(
        self,
        db_session: AsyncSession,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """Symlink pointing outside upload dir returns 404."""
        from webapp.services.asset_service import AssetService

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()

        # Create secret file outside upload dir
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("sensitive data")

        # Create symlink inside upload dir
        link_dir = upload_dir / "di-tracks"
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / "evil.wav"
        link.symlink_to(secret_file)

        service = AssetService(
            secret_key="test-secret",
            upload_base=upload_dir,
        )
        signature = service.generate_signed_url(
            file_path="di-tracks/evil.wav",
            user_id=test_user.id,
            expires_in=3600,
        )

        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/files/{signature}")

        assert response.status_code == 404
