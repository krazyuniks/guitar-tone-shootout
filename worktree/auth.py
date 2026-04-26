"""Authentication persistence module for worktree management.

Handles shared authentication across all worktrees using a centralized
auth file stored in the worktrees parent directory.
"""

import contextlib
import json
import webbrowser
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import httpx

from .config import get_worktree_root


class AuthStatus(NamedTuple):
    """Auth status result."""

    valid: bool
    authenticated: bool
    username: str | None
    expires_at: datetime | None
    expires_in_hours: float | None
    message: str


def get_auth_file_path() -> Path:
    """Get the auth file path.

    Returns the path to .gts-auth.json in the worktrees parent directory.
    This ensures all worktrees share the same auth data.
    """
    try:
        root = get_worktree_root()
        return root / ".gts-auth.json"
    except Exception:
        # Fallback to current directory's parent
        return Path.cwd().parent / ".gts-auth.json"


def check_auth_file_permissions(path: Path) -> tuple[bool, str]:
    """Check if auth file has secure permissions.

    The auth file should have mode 0600 (owner read/write only) to protect
    sensitive OAuth tokens from other users on the system.

    Args:
        path: Path to the auth file.

    Returns:
        Tuple of (is_secure: bool, message: str).
    """
    import os
    import stat

    try:
        file_stat = path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Check if file is readable/writable by group or others
        insecure_bits = stat.S_IRWXG | stat.S_IRWXO  # group and other permissions
        if mode & insecure_bits:
            actual_mode = oct(mode)
            return (
                False,
                f"Auth file has insecure permissions ({actual_mode}). Run: chmod 600 {path}",
            )

        # Check if file is owned by current user
        if file_stat.st_uid != os.getuid():
            return (
                False,
                "Auth file is not owned by current user. This may indicate a security issue.",
            )

        return True, "Auth file permissions are secure (0600, owner-only)"
    except OSError as e:
        return False, f"Cannot check auth file permissions: {e}"


def fix_auth_file_permissions(path: Path) -> bool:
    """Fix auth file permissions to 0600 (owner read/write only).

    Args:
        path: Path to the auth file.

    Returns:
        True if permissions were fixed, False on error.
    """
    try:
        path.chmod(0o600)
        return True
    except OSError:
        return False


def read_auth_file() -> dict[str, Any] | None:
    """Read auth data from the shared auth file.

    Also validates and fixes file permissions if insecure.

    Returns:
        Dict with auth data if file exists and is valid, None otherwise.
    """
    auth_path = get_auth_file_path()
    if not auth_path.exists():
        return None

    # Check and fix permissions
    is_secure, message = check_auth_file_permissions(auth_path)
    if not is_secure:
        # Attempt to fix permissions automatically
        if fix_auth_file_permissions(auth_path):
            pass  # Fixed silently
        else:
            # Log warning but continue - the data is still readable
            import sys

            print(f"Warning: {message}", file=sys.stderr)

    try:
        auth_data: dict[str, Any] = json.loads(auth_path.read_text(encoding="utf-8"))
        return auth_data
    except (json.JSONDecodeError, OSError):
        return None


def check_auth_status() -> AuthStatus:
    """Check the current auth status from the shared auth file.

    Returns:
        AuthStatus with validity info and human-readable message.
    """
    auth_data = read_auth_file()

    if auth_data is None:
        return AuthStatus(
            valid=False,
            authenticated=False,
            username=None,
            expires_at=None,
            expires_in_hours=None,
            message="No saved auth data. Run `just t3k-auth` to authenticate.",
        )

    # Check we have tokens (access_token is the minimum requirement)
    if not auth_data.get("access_token"):
        return AuthStatus(
            valid=False,
            authenticated=False,
            username=auth_data.get("username"),
            expires_at=None,
            expires_in_hours=None,
            message="Invalid auth file format. Re-authenticate with `just t3k-auth`.",
        )

    # Parse expiration time (field name varies: token_expires_at or expires_at)
    expires_at_raw = auth_data.get("token_expires_at") or auth_data.get("expires_at")
    username = auth_data.get("username", "unknown")

    if not expires_at_raw:
        # No expiration info — tokens are valid until revoked
        return AuthStatus(
            valid=True,
            authenticated=True,
            username=username,
            expires_at=None,
            expires_in_hours=None,
            message=f"Auth valid for {username}. No expiration set.",
        )

    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
        # Handle timezone-naive datetimes
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        # Can't parse expiration but tokens exist — treat as valid
        return AuthStatus(
            valid=True,
            authenticated=True,
            username=username,
            expires_at=None,
            expires_in_hours=None,
            message=f"Auth valid for {username}. Could not parse expiration.",
        )

    now = datetime.now(UTC)
    is_valid = expires_at > now + timedelta(minutes=5)  # 5 min buffer

    if not is_valid:
        return AuthStatus(
            valid=False,
            authenticated=False,
            username=auth_data.get("username"),
            expires_at=expires_at,
            expires_in_hours=0,
            message="T3K tokens have expired. Run `just t3k-auth` to re-authenticate.",
        )

    # Calculate hours remaining
    expires_delta = expires_at - now
    expires_in_hours = expires_delta.total_seconds() / 3600

    # Determine status message
    if expires_in_hours < 1:
        message = f"Auth valid for {username}. Expiring in less than 1 hour!"
    elif expires_in_hours < 24:
        message = f"Auth valid for {username}. Expiring in {expires_in_hours:.1f} hours."
    else:
        days = expires_in_hours / 24
        message = f"Auth valid for {username}. Expires in {days:.1f} days."

    return AuthStatus(
        valid=True,
        authenticated=True,
        username=username,
        expires_at=expires_at,
        expires_in_hours=round(expires_in_hours, 2),
        message=message,
    )


def start_login_flow(webapp_url: str = "http://localhost:8000") -> bool:
    """Start the OAuth login flow by opening Chrome browser.

    This opens the T3K OAuth login page in Chrome (required for proxy setup).
    After successful auth, the callback will automatically save tokens to
    the shared auth file.

    Args:
        webapp_url: Webapp URL to use for OAuth (default: localhost:8000).

    Returns:
        True if browser was opened successfully, False otherwise.
    """
    import subprocess
    import sys

    login_url = f"{webapp_url}/auth/login/t3k"

    try:
        # Use Chrome explicitly (required for proxy setup on dev machines)
        if sys.platform == "darwin":
            # macOS: use 'open' with Chrome application
            subprocess.run(
                ["open", "-a", "Google Chrome", login_url],
                check=True,
            )
        elif sys.platform == "win32":
            # Windows: use start with Chrome
            subprocess.run(
                ["start", "chrome", login_url],
                shell=True,
                check=True,
            )
        else:
            # Linux: try google-chrome or chromium
            try:
                subprocess.run(["google-chrome", login_url], check=True)
            except FileNotFoundError:
                subprocess.run(["chromium", login_url], check=True)
        return True
    except Exception:
        # Fallback to default browser if Chrome not available
        try:
            webbrowser.open(login_url)
            return True
        except Exception:
            return False


def restore_session(webapp_url: str = "http://localhost:8000") -> tuple[bool, str]:
    """Restore session from saved auth file via webapp API.

    Calls the webapp's restore-session endpoint which reads the auth file
    and creates a local user/session.

    Args:
        webapp_url: Webapp URL to call (default: localhost:8000).

    Returns:
        Tuple of (success: bool, message: str).
    """
    # First check if we have valid auth data
    status = check_auth_status()
    if not status.valid:
        return False, status.message

    # Call the restore-session endpoint
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{webapp_url}/auth/restore-session")

            if response.status_code == 200:
                data = response.json()
                return True, data.get("message", "Session restored successfully")
            elif response.status_code == 404:
                return False, "No saved auth data found. Run `just t3k-auth` first."
            elif response.status_code == 401:
                return False, "Saved tokens have expired. Run `just t3k-auth` again."
            else:
                return False, f"Restore failed: {response.status_code}"

    except httpx.ConnectError:
        return False, f"Cannot connect to webapp at {webapp_url}. Is it running?"
    except httpx.RequestError as e:
        return False, f"Request failed: {e}"


def restore_session_browser(frontend_url: str = "http://localhost:4341") -> bool:
    """Open browser to restore session with cookie.

    The API restore-session only sets the cookie in the API response.
    To get the cookie in the browser, we need to navigate to the
    GET version which redirects with Set-Cookie header.

    Args:
        frontend_url: Frontend URL (nginx) to use for browser redirect.

    Returns:
        True if browser was opened successfully, False otherwise.
    """
    import subprocess
    import sys

    restore_url = f"{frontend_url}/auth/restore-session"

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", restore_url], check=True)
        elif sys.platform == "win32":
            subprocess.run(["start", restore_url], shell=True, check=True)
        else:
            try:
                subprocess.run(["xdg-open", restore_url], check=True)
            except FileNotFoundError:
                webbrowser.open(restore_url)
        return True
    except Exception:
        try:
            webbrowser.open(restore_url)
            return True
        except Exception:
            return False


def get_webapp_url_for_worktree(worktree_path: Path | None = None) -> str:
    """Get the webapp URL for a worktree.

    Reads the port from the worktree's environment or registry.

    Args:
        worktree_path: Path to worktree, or None for current directory.

    Returns:
        Webapp URL (e.g., "http://localhost:8030").
    """
    from .registry import get_worktree_by_path

    if worktree_path is None:
        worktree_path = Path.cwd()

    try:
        worktree = get_worktree_by_path(worktree_path)
        if worktree:
            return f"http://localhost:{worktree.ports.webapp}"
    except Exception:
        pass

    # Fallback: try to read PUBLIC_URL from .env.worktree
    env_file = worktree_path / ".env.worktree"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("PUBLIC_URL="):
                return line.split("=", 1)[1].strip()

    # Default fallback
    return "http://localhost:8000"


def check_auth_from_api(webapp_url: str) -> AuthStatus:
    """Check auth status via webapp API.

    This hits the /auth/status endpoint which reads from the auth file
    and returns detailed status information.

    Args:
        webapp_url: Webapp URL to query.

    Returns:
        AuthStatus with validity info.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{webapp_url}/auth/status")

            if response.status_code == 200:
                data = response.json()
                expires_at = None
                if data.get("expires_at"):
                    with contextlib.suppress(ValueError):
                        expires_at = datetime.fromisoformat(data["expires_at"])

                return AuthStatus(
                    valid=data.get("valid", False),
                    authenticated=data.get("authenticated", False),
                    username=data.get("username"),
                    expires_at=expires_at,
                    expires_in_hours=data.get("expires_in_hours"),
                    message=data.get("message", ""),
                )
            else:
                return AuthStatus(
                    valid=False,
                    authenticated=False,
                    username=None,
                    expires_at=None,
                    expires_in_hours=None,
                    message=f"API returned status {response.status_code}",
                )

    except httpx.ConnectError:
        # Fall back to local file check
        return check_auth_status()
    except Exception as e:
        return AuthStatus(
            valid=False,
            authenticated=False,
            username=None,
            expires_at=None,
            expires_in_hours=None,
            message=f"Error checking auth: {e}",
        )
