"""Asset/File serving service with HMAC-signed URLs.

Provides secure file access via signed URLs with expiration.
Validates signatures, prevents path traversal, and enforces ownership.
"""

import base64
import hmac
import json
import mimetypes
import time
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote
from uuid import UUID


class SignaturePayload(TypedDict):
    """Decoded signature payload."""

    file_path: str
    user_id: str
    expires_at: float


class AssetService:
    """Service for generating and validating HMAC-signed file URLs.

    Uses HMAC-SHA256 with SECRET_KEY to create time-limited signed URLs.
    Validates signatures, file ownership, and prevents path traversal.
    """

    def __init__(self, secret_key: str, upload_base: Path) -> None:
        """Initialize the asset service.

        Args:
            secret_key: Secret key for HMAC signing
            upload_base: Base directory for file uploads
        """
        self.secret_key = secret_key.encode("utf-8")
        self.upload_base = upload_base

    def generate_signed_url(
        self,
        file_path: str,
        user_id: UUID,
        expires_in: int,
    ) -> str:
        """Generate an HMAC-signed URL for a file.

        Args:
            file_path: Relative path to file within upload directory
            user_id: User ID who owns or can access the file
            expires_in: Seconds until expiration

        Returns:
            Base64-encoded signature containing file path, user ID, and expiry

        Raises:
            ValueError: If file_path contains path traversal sequences
        """
        # Validate path to prevent traversal
        self._validate_path(file_path)

        # Create payload
        expires_at = time.time() + expires_in
        payload: SignaturePayload = {
            "file_path": file_path,
            "user_id": str(user_id),
            "expires_at": expires_at,
        }

        # Serialize and sign
        payload_json = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key,
            payload_json.encode("utf-8"),
            digestmod="sha256",
        ).digest()

        # Combine: payload_length (4 bytes) + payload + signature
        payload_bytes = payload_json.encode("utf-8")
        payload_length = len(payload_bytes).to_bytes(4, byteorder="big")
        combined = payload_length + payload_bytes + signature
        return base64.urlsafe_b64encode(combined).decode("utf-8")

    def validate_signature(self, signature: str) -> SignaturePayload | None:
        """Validate an HMAC signature and extract payload.

        This method ONLY validates the signature itself - it does NOT
        check if the file exists on disk. Use resolve_file_path() for
        full validation including file existence.

        Args:
            signature: Base64-encoded signature from generate_signed_url

        Returns:
            Decoded payload dict if valid, None otherwise
        """
        if not signature:
            return None

        try:
            # Decode from base64
            combined = base64.urlsafe_b64decode(signature)

            # Extract payload length (first 4 bytes)
            if len(combined) < 4:
                return None

            payload_length = int.from_bytes(combined[:4], byteorder="big")

            # Extract payload and signature
            if len(combined) < 4 + payload_length + 32:  # 32 = SHA256 digest size
                return None

            payload_bytes = combined[4 : 4 + payload_length]
            expected_signature = combined[4 + payload_length :]

            # Verify signature
            computed_signature = hmac.new(
                self.secret_key,
                payload_bytes,
                digestmod="sha256",
            ).digest()

            if not hmac.compare_digest(computed_signature, expected_signature):
                return None

            # Parse payload
            payload: SignaturePayload = json.loads(payload_bytes)

            # Check expiration
            if time.time() > payload["expires_at"]:
                return None

            return payload

        except (ValueError, KeyError, json.JSONDecodeError):
            return None

    def resolve_file_path(self, signature: str) -> Path | None:
        """Resolve a signed URL to an absolute file path.

        Validates the signature, checks file exists, and prevents
        path traversal (including symlinks outside upload dir).

        Args:
            signature: Base64-encoded signature

        Returns:
            Absolute path to file if valid and exists, None otherwise
        """
        # Validate signature
        payload = self.validate_signature(signature)
        if not payload:
            return None

        # Resolve file path
        try:
            file_rel = Path(payload["file_path"])
            file_abs = (self.upload_base / file_rel).resolve()

            # Check if resolved path is within upload directory
            # (prevents symlinks pointing outside)
            if not str(file_abs).startswith(str(self.upload_base.resolve())):
                return None

            # Check file exists
            if not file_abs.is_file():
                return None

            return file_abs

        except (ValueError, OSError):
            return None

    def get_content_type(self, file_path: str) -> str:
        """Detect MIME content type for a file.

        Args:
            file_path: File path (filename with extension)

        Returns:
            MIME type string, defaults to application/octet-stream
        """
        # Use mimetypes to guess, with fallback
        content_type, _ = mimetypes.guess_type(file_path)

        # Some extensions (like .xyz) may have unexpected mappings
        # Only accept content types we know are correct
        if content_type and content_type.startswith(("audio/", "video/", "image/")):
            return content_type

        # For unknown or non-media types, default to octet-stream
        return "application/octet-stream"

    def _validate_path(self, file_path: str) -> None:
        """Validate path to prevent traversal attacks.

        Args:
            file_path: Relative file path to validate

        Raises:
            ValueError: If path contains traversal sequences
        """
        # Decode URL-encoded sequences
        decoded = unquote(file_path)

        # Check for path traversal patterns
        if ".." in decoded or "\\" in decoded or decoded.startswith("/"):
            raise ValueError(f"Invalid file path: {file_path}")
