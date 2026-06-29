#!/usr/bin/env python3
"""T3K auth helper (standalone, decoupled from the retired worktree package).

Two operations, matching what `just t3k-auth` / `just t3k-auth-status` need:

  status   - read the shared .gts-auth.json and report token validity/expiry.
             Exit 0 when valid, 1 otherwise. --quiet suppresses output.
  restore  - POST /auth/restore-session to the running webapp so it mints a
             local session from the saved tokens.

The shared auth file lives at the parent of this checkout
(guitar-tone-worktrees/.gts-auth.json), shared by main and feature worktrees.
The login flow itself is scripts/t3k_login.py (headless Chromium); this helper
only checks and restores.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def _auth_file() -> Path:
    """The shared .gts-auth.json at the parent of the current checkout."""
    return Path.cwd().resolve().parent / ".gts-auth.json"


def _read_auth() -> dict[str, Any] | None:
    path = _auth_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def check_status() -> tuple[bool, str | None, datetime | None, float | None]:
    """Return (valid, username, expires_at, expires_in_hours) from the auth file."""
    data = _read_auth()
    if data is None:
        return False, None, None, None
    if not data.get("access_token"):
        return False, data.get("username"), None, None
    username = data.get("username", "unknown")
    raw = data.get("token_expires_at") or data.get("expires_at")
    if not raw:
        return True, username, None, None
    try:
        expires_at = datetime.fromisoformat(raw)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return True, username, None, None
    now = datetime.now(UTC)
    expires_in = (expires_at - now).total_seconds() / 3600.0
    return expires_at > now, username, expires_at, expires_in


def _webapp_url() -> str:
    """The webapp URL: PUBLIC_URL from the env (set by scripts/worktree/current-env),
    else the localhost default."""
    return os.getenv("PUBLIC_URL", "http://localhost:8000")


def restore() -> tuple[bool, str]:
    valid, username, _, _ = check_status()
    if not valid:
        return False, "No valid saved auth. Run `just t3k-auth` (or `just t3k-login`) first."
    url = f"{_webapp_url()}/auth/restore-session"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url)
    except httpx.ConnectError:
        return False, f"Cannot connect to webapp at {_webapp_url()}. Is it running?"
    except httpx.RequestError as exc:
        return False, f"Request failed: {exc}"
    if resp.status_code == 200:
        msg = resp.json().get("message", "Session restored")
        return True, f"{msg} ({username})"
    if resp.status_code == 404:
        return False, "No saved auth data found. Run `just t3k-auth` first."
    if resp.status_code == 401:
        return False, "Saved tokens have expired. Run `just t3k-auth` again."
    return False, f"Restore failed: {resp.status_code}"


def _cmd_status(quiet: bool) -> int:
    valid, username, expires_at, expires_in = check_status()
    if quiet:
        return 0 if valid else 1
    path = _auth_file()
    print(f"valid:     {'yes' if valid else 'no (expired or missing)'}")
    if username:
        print(f"username:  {username}")
    if expires_at:
        print(f"expires:   {expires_at.isoformat()}")
        if expires_in is not None:
            print(f"remaining: {expires_in:.1f} hours" if expires_in < 24
                  else f"remaining: {expires_in / 24:.1f} days")
    print(f"auth file: {path}")
    return 0 if valid else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="GTS T3K auth helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="check saved auth validity and expiry")
    s.add_argument("--quiet", "-q", action="store_true", help="exit code only")
    sub.add_parser("restore", help="restore a session into the running webapp")
    args = parser.parse_args()
    if args.cmd == "status":
        return _cmd_status(args.quiet)
    if args.cmd == "restore":
        ok, msg = restore()
        print(msg)
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
