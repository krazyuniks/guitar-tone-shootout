"""Auth gate — preflight check before any source API call.

Reads plaintext auth_status from .gts-auth.json. No decryption, no network.
"""

import json
import logging
from pathlib import Path

from core.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)


def check_auth_status(auth_file_path: str) -> SourceAuthStatus:
    """Read auth_status from auth file. No decryption, no API calls.

    Returns SourceAuthStatus.UNKNOWN if the file is missing, unreadable,
    or doesn't contain a recognised auth_status value.
    """
    path = Path(auth_file_path)
    if not path.exists():
        logger.debug("Auth file not found: %s", auth_file_path)
        return SourceAuthStatus.UNKNOWN

    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Auth file unreadable: %s", auth_file_path)
        return SourceAuthStatus.UNKNOWN

    raw_status = data.get("auth_status")
    if raw_status is None:
        # Backwards-compat: auth files written before auth_status existed
        if data.get("access_token"):
            return SourceAuthStatus.VALID
        return SourceAuthStatus.UNKNOWN

    try:
        return SourceAuthStatus(raw_status)
    except ValueError:
        logger.warning("Unrecognised auth_status in %s: %s", auth_file_path, raw_status)
        return SourceAuthStatus.UNKNOWN
