"""Vercel Security Checkpoint cookie loader.

When Vercel's bot protection triggers a JS challenge, HTTP clients get a 403.
Since the worker container doesn't have a browser, we solve the challenge on
the host (same external IP) using Playwright and save cookies to a file.
The API client loads these cookies and sends them with every request.

Run `just solve-vercel` on the host to refresh cookies.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cookie file path — overridable via env var.
# Inside the worker container this resolves to /worktrees/.vercel-cookies.json
# (the worktrees parent dir is mounted at /worktrees).
_DEFAULT_COOKIE_FILE = os.getenv(
    "VERCEL_COOKIES_FILE",
    "/worktrees/.vercel-cookies.json",
)


def is_vercel_challenge(status_code: int, body: str) -> bool:
    """Detect a Vercel Security Checkpoint response."""
    return status_code == 403 and "Vercel Security Checkpoint" in body


def load_cookies(cookie_file: str | None = None) -> dict[str, str]:
    """Load Vercel cookies from the cookie file.

    Returns a dict of {name: value} suitable for httpx cookies parameter.
    Returns empty dict if file doesn't exist or is invalid.
    """
    path = Path(cookie_file or _DEFAULT_COOKIE_FILE)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text())
        cookies = {c["name"]: c["value"] for c in data}
        logger.info("Loaded %d Vercel cookies from %s", len(cookies), path)
        return cookies
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Failed to parse Vercel cookies from %s", path)
        return {}


def solve_challenge(url: str = "https://www.tone3000.com") -> bool:
    """Signal that a Vercel challenge was detected.

    The actual solving happens on the host via `just solve-vercel`.
    This function just logs the situation and returns False so the
    caller knows to raise an appropriate error.
    """
    logger.error(
        "Vercel challenge detected for %s — run `just solve-vercel` on the host "
        "to solve it, then retry the sync",
        url,
    )
    return False
