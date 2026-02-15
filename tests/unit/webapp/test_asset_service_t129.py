"""Unit tests for AssetService (T129).

Tests HMAC-signed URL generation, signature validation,
path traversal prevention, and ownership checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

from webapp.services.asset_service import AssetService


@pytest.fixture
def upload_dir(tmp_path: Path) -> Path:
    """Create a temporary upload directory."""
    upload = tmp_path / "uploads"
    upload.mkdir()
    return upload


@pytest.fixture
def secret_key() -> str:
    return "test-secret-key-for-hmac"


@pytest.fixture
def service(upload_dir: Path, secret_key: str) -> AssetService:
    """Create an AssetService instance with test configuration."""
    return AssetService(secret_key=secret_key, upload_base=upload_dir)


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def other_user_id() -> UUID:
    return uuid4()


@pytest.mark.asyncio
class TestGenerateSignedUrl:
    """Test AssetService.generate_signed_url produces valid HMAC signatures."""

    async def test_returns_non_empty_signature(self, service: AssetService, user_id: UUID) -> None:
        """generate_signed_url returns a non-empty string."""
        result = service.generate_signed_url(
            file_path="di-tracks/user1/track.wav",
            user_id=user_id,
            expires_in=3600,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_different_files_produce_different_signatures(
        self, service: AssetService, user_id: UUID
    ) -> None:
        """Different file paths produce different signatures."""
        sig1 = service.generate_signed_url(
            file_path="di-tracks/a.wav",
            user_id=user_id,
            expires_in=3600,
        )
        sig2 = service.generate_signed_url(
            file_path="di-tracks/b.wav",
            user_id=user_id,
            expires_in=3600,
        )
        assert sig1 != sig2

    async def test_different_users_produce_different_signatures(
        self, service: AssetService, user_id: UUID, other_user_id: UUID
    ) -> None:
        """Different user IDs produce different signatures."""
        sig1 = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=3600,
        )
        sig2 = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=other_user_id,
            expires_in=3600,
        )
        assert sig1 != sig2

    async def test_signature_includes_expiry(self, service: AssetService, user_id: UUID) -> None:
        """Signatures generated with different expiry windows differ."""
        sig1 = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=60,
        )
        sig2 = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=7200,
        )
        assert sig1 != sig2


@pytest.mark.asyncio
class TestValidateSignature:
    """Test signature validation — expiry, tampering, invalid signatures."""

    async def test_valid_signature_returns_file_info(
        self, service: AssetService, user_id: UUID, upload_dir: Path
    ) -> None:
        """A valid, non-expired signature returns file path and user_id."""
        # Create actual file in upload dir
        file_rel = "di-tracks/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_abs.write_bytes(b"\x00" * 100)

        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=user_id,
            expires_in=3600,
        )

        result = service.validate_signature(signature)
        assert result is not None
        assert result["file_path"] == file_rel
        assert result["user_id"] == str(user_id)

    async def test_expired_signature_returns_none(
        self, service: AssetService, user_id: UUID
    ) -> None:
        """An expired signature is rejected (returns None)."""
        signature = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=-1,  # Already expired
        )

        result = service.validate_signature(signature)
        assert result is None

    async def test_tampered_signature_returns_none(
        self, service: AssetService, user_id: UUID
    ) -> None:
        """A tampered signature is rejected."""
        signature = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=3600,
        )

        # Tamper with the signature
        tampered = signature[:-4] + "XXXX"

        result = service.validate_signature(tampered)
        assert result is None

    async def test_completely_invalid_signature_returns_none(self, service: AssetService) -> None:
        """Garbage input is rejected."""
        result = service.validate_signature("not-a-valid-signature-at-all")
        assert result is None

    async def test_empty_signature_returns_none(self, service: AssetService) -> None:
        """Empty string is rejected."""
        result = service.validate_signature("")
        assert result is None

    async def test_wrong_secret_key_rejects_signature(
        self, upload_dir: Path, user_id: UUID
    ) -> None:
        """A signature created with one key is rejected by a different key."""
        service1 = AssetService(secret_key="key-one", upload_base=upload_dir)
        service2 = AssetService(secret_key="key-two", upload_base=upload_dir)

        signature = service1.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=3600,
        )

        result = service2.validate_signature(signature)
        assert result is None


@pytest.mark.asyncio
class TestPathTraversalPrevention:
    """Test that path traversal attacks are rejected."""

    async def test_rejects_dot_dot_path(self, service: AssetService, user_id: UUID) -> None:
        """Paths containing '..' are rejected."""
        with pytest.raises((ValueError, Exception)):
            service.generate_signed_url(
                file_path="../../../etc/passwd",
                user_id=user_id,
                expires_in=3600,
            )

    async def test_rejects_absolute_path(self, service: AssetService, user_id: UUID) -> None:
        """Absolute paths are rejected."""
        with pytest.raises((ValueError, Exception)):
            service.generate_signed_url(
                file_path="/etc/passwd",
                user_id=user_id,
                expires_in=3600,
            )

    async def test_rejects_backslash_traversal(self, service: AssetService, user_id: UUID) -> None:
        """Windows-style path traversal with backslashes is rejected."""
        with pytest.raises((ValueError, Exception)):
            service.generate_signed_url(
                file_path="..\\..\\etc\\passwd",
                user_id=user_id,
                expires_in=3600,
            )

    async def test_rejects_encoded_traversal(self, service: AssetService, user_id: UUID) -> None:
        """URL-encoded path traversal sequences are rejected."""
        with pytest.raises((ValueError, Exception)):
            service.generate_signed_url(
                file_path="%2e%2e/%2e%2e/etc/passwd",
                user_id=user_id,
                expires_in=3600,
            )

    async def test_rejects_symlink_outside_upload_dir(
        self, service: AssetService, user_id: UUID, upload_dir: Path, tmp_path: Path
    ) -> None:
        """Symlinks pointing outside the upload directory are rejected on resolve."""
        # Create a file outside upload dir
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")

        # Create symlink inside upload dir pointing outside
        symlink = upload_dir / "di-tracks" / "evil_link.wav"
        symlink.parent.mkdir(parents=True, exist_ok=True)
        symlink.symlink_to(outside_file)

        signature = service.generate_signed_url(
            file_path="di-tracks/evil_link.wav",
            user_id=user_id,
            expires_in=3600,
        )

        # resolve_file_path should reject the symlink
        resolved = service.resolve_file_path(signature)
        assert resolved is None

    async def test_accepts_valid_relative_path(
        self, service: AssetService, user_id: UUID, upload_dir: Path
    ) -> None:
        """A valid relative path within the upload dir is accepted."""
        file_rel = "di-tracks/user1/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_abs.write_bytes(b"\x00" * 100)

        # Should not raise
        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=user_id,
            expires_in=3600,
        )
        assert signature is not None


@pytest.mark.asyncio
class TestOwnershipValidation:
    """Test that file ownership is validated correctly."""

    async def test_owner_can_access_own_file(
        self, service: AssetService, user_id: UUID, upload_dir: Path
    ) -> None:
        """The file owner can access their file."""
        file_rel = "di-tracks/track.wav"
        file_abs = upload_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_abs.write_bytes(b"\x00" * 100)

        signature = service.generate_signed_url(
            file_path=file_rel,
            user_id=user_id,
            expires_in=3600,
        )

        result = service.validate_signature(signature)
        assert result is not None
        assert result["user_id"] == str(user_id)

    async def test_signature_binds_to_specific_user(
        self, service: AssetService, user_id: UUID, other_user_id: UUID
    ) -> None:
        """A signature generated for one user cannot be used by another."""
        signature = service.generate_signed_url(
            file_path="di-tracks/track.wav",
            user_id=user_id,
            expires_in=3600,
        )

        result = service.validate_signature(signature)
        assert result is not None
        # The signature encodes the user_id — a different user should not match
        assert result["user_id"] == str(user_id)
        assert result["user_id"] != str(other_user_id)


@pytest.mark.asyncio
class TestContentTypeDetection:
    """Test MIME type detection for file serving."""

    async def test_wav_content_type(self, service: AssetService) -> None:
        """WAV files return audio/wav content type."""
        content_type = service.get_content_type("track.wav")
        assert content_type in ("audio/wav", "audio/x-wav")

    async def test_mp3_content_type(self, service: AssetService) -> None:
        """MP3 files return audio/mpeg content type."""
        content_type = service.get_content_type("track.mp3")
        assert content_type == "audio/mpeg"

    async def test_flac_content_type(self, service: AssetService) -> None:
        """FLAC files return audio/flac content type."""
        content_type = service.get_content_type("track.flac")
        assert content_type in ("audio/flac", "audio/x-flac")

    async def test_unknown_extension_defaults_to_octet_stream(self, service: AssetService) -> None:
        """Unknown file types default to application/octet-stream."""
        content_type = service.get_content_type("file.xyz")
        assert content_type == "application/octet-stream"
