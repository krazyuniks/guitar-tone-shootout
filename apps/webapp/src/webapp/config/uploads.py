"""Upload directory configuration for file uploads.

Provides configurable upload paths for testing and production.
"""

from pathlib import Path

# Module-level override for testing
_upload_base_override: Path | None = None


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
    return Path("/app/uploads")
