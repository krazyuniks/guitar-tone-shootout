"""Source authentication status value object.

Tracks whether a source's OAuth tokens are healthy enough to make API calls.
Stored as plaintext in .gts-auth.json so any component can read it without decryption.
"""

from enum import Enum


class SourceAuthStatus(str, Enum):
    """Authentication health of a source's OAuth tokens.

    Written by the scheduler refresh job. Read by sync jobs and admin API
    as a preflight gate — no API calls proceed unless status is VALID or
    EXPIRING_SOON.
    """

    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    REFRESH_FAILED = "refresh_failed"
    LOGIN_REQUIRED = "login_required"
    UNKNOWN = "unknown"

    def can_proceed(self) -> bool:
        """Return True if API calls are safe to make."""
        return self != SourceAuthStatus.LOGIN_REQUIRED

    def needs_login(self) -> bool:
        """Return True if manual re-authentication is needed."""
        return self == SourceAuthStatus.LOGIN_REQUIRED
