"""Upload directory and secret key configuration for file uploads and asset signing.

Provides configurable upload paths and secret keys for testing and production.
"""

import os
from pathlib import Path

from webapp.config.secrets import get_app_secret_key

# Module-level overrides for testing
_upload_base_override: Path | None = None
_secret_key_override: str | None = None


def set_upload_base_override(path: Path | None) -> None:
    """Set upload base directory override for testing.

    Args:
        path: Base directory for uploads, or None to use default
    """
    global _upload_base_override
    _upload_base_override = path


def get_upload_base() -> Path:
    """Get the base directory for uploads.

    Returns test override if set, otherwise production default.

    Returns:
        Base directory path for uploads
    """
    if _upload_base_override is not None:
        return _upload_base_override
    return Path(os.environ["GTS_STORAGE_ROOT"]) / "uploads"


def set_secret_key_override(key: str | None) -> None:
    """Set secret key override for testing.

    Args:
        key: Secret key for HMAC signing, or None to use default
    """
    global _secret_key_override
    _secret_key_override = key


def get_secret_key() -> str:
    """Get the secret key for HMAC signing.

    Returns test override if set, otherwise the application secret key.

    Returns:
        Secret key string
    """
    if _secret_key_override is not None:
        return _secret_key_override
    return get_app_secret_key()
