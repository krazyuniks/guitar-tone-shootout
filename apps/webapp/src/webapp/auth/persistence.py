"""Auth file persistence for .gts-auth.json.

Provides save/load functionality for authentication data that can be
shared across multiple worktrees. The auth file contains encrypted
OAuth tokens and user information.
"""

import json
import os
from pathlib import Path
from typing import Any


class AuthFilePersistence:
    """Handles reading and writing .gts-auth.json file.

    The auth file stores encrypted tokens and user information that can
    be shared across multiple git worktrees. File permissions are set
    to 0600 (owner read/write only) for security.
    """

    def __init__(self, auth_file_path: str | None = None) -> None:
        """Initialize auth file persistence.

        Args:
            auth_file_path: Path to .gts-auth.json file.
                           If None, reads from GTS_AUTH_FILE env var,
                           or defaults to /.gts-auth.json (Docker).
        """
        if auth_file_path is None:
            auth_file_path = os.environ.get(
                "GTS_AUTH_FILE", "/.gts-auth.json"
            )

        self.auth_file_path = auth_file_path

    def save(self, auth_data: dict[str, Any]) -> None:
        """Save auth data to .gts-auth.json file.

        Args:
            auth_data: Dictionary containing authentication data:
                       - user_id: User UUID (string)
                       - username: Username (string)
                       - access_token: Encrypted access token (string)
                       - refresh_token: Encrypted refresh token (optional)
                       - expires_at: Token expiration timestamp (optional)
        """
        # Write auth data to file
        with open(self.auth_file_path, "w") as f:
            json.dump(auth_data, f, indent=2)

        # Set secure file permissions (0600 - owner read/write only)
        os.chmod(self.auth_file_path, 0o600)

    def load(self) -> dict[str, Any] | None:
        """Load auth data from .gts-auth.json file.

        Returns:
            Auth data dictionary if file exists, None otherwise.

        Raises:
            json.JSONDecodeError: If file contains invalid JSON
        """
        auth_path = Path(self.auth_file_path)

        # Return None if file doesn't exist
        if not auth_path.exists():
            return None

        # Read and parse JSON
        with open(auth_path) as f:
            return json.load(f)

    def delete(self) -> None:
        """Delete .gts-auth.json file if it exists."""
        auth_path = Path(self.auth_file_path)

        if auth_path.exists():
            auth_path.unlink()
