#!/usr/bin/env python3
"""T3K Login — headless Chromium authentication through the GTS callback.

Usage: just t3k-login

Launches headless Chromium, navigates through the GTS login endpoint, fills
email, prompts for the 6-digit code, and lets the GTS callback save encrypted
tokens to .gts-auth.json.

User-facing wrapper: `just t3k-auth` is the canonical entry point.
This script exists for direct login when status and restore are handled
separately.

The shared auth file is written by the webapp callback. This keeps token
exchange in one place and avoids scraping provider-specific browser storage.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chromium_executable import find_chromium_executable

# Auth file at worktree root (parent of any worktree dir)
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
AUTH_FILE = WORKTREE_ROOT / ".gts-auth.json"
LOGIN_EMAIL = "brewsterbear@gmail.com"


def get_public_url() -> str:
    """The current worktree's public URL.

    Set by scripts/worktree/current-env (sourced in the just t3k-login recipe);
    falls back to the main nginx entry point.
    """
    return os.getenv("PUBLIC_URL", "http://localhost:9000")


def auth_file_is_fresh(started_at: datetime) -> bool:
    """Return whether the GTS callback wrote a usable auth file."""
    if not AUTH_FILE.exists():
        return False

    try:
        auth_data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if not auth_data.get("access_token"):
        return False

    saved_at_raw = auth_data.get("saved_at")
    if saved_at_raw:
        try:
            saved_at = datetime.fromisoformat(saved_at_raw)
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=UTC)
            if saved_at < started_at - timedelta(seconds=5):
                return False
        except (TypeError, ValueError):
            return False

    expires_at_raw = auth_data.get("token_expires_at") or auth_data.get("expires_at")
    if not expires_at_raw:
        return True

    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return True

    return expires_at > datetime.now(UTC) + timedelta(minutes=5)


def main() -> None:
    """Run the T3K login flow."""
    try:
        from cryptography.fernet import Fernet
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: uv sync --group host")
        sys.exit(1)

    # Import check only: token encryption happens in the webapp callback.
    _ = Fernet
    browser_executable = find_chromium_executable()
    if browser_executable is None:
        print("Missing browser: install Google Chrome or Chromium")
        sys.exit(1)

    started_at = datetime.now(UTC)
    public_url = get_public_url()
    print(f"T3K Login — {LOGIN_EMAIL}")
    print(f"Auth file: {AUTH_FILE}")
    print(f"GTS URL: {public_url}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=browser_executable,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page()

        print("Opening GTS login flow...")
        page.goto(f"{public_url}/auth/login/t3k", wait_until="networkidle")

        # Fill email
        print(f"Filling email: {LOGIN_EMAIL}")
        email_input = page.locator('input[type="email"]')
        email_input.fill(LOGIN_EMAIL)

        # Submit email
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()
        page.wait_for_load_state("networkidle")

        # Prompt for verification code
        print()
        code = os.getenv("T3K_LOGIN_CODE", "").strip()
        if not code:
            code = input("Enter 6-digit code from email: ").strip()
        if len(code) != 6 or not code.isdigit():
            print("Error: Expected 6-digit numeric code")
            browser.close()
            sys.exit(1)

        # Fill code — T3K uses 6 individual digit inputs
        for i, digit in enumerate(code):
            digit_input = page.get_by_role("textbox", name=f"Digit {i + 1} of 6")
            digit_input.fill(digit)

        # Submit code
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()

        # Wait for the GTS callback to exchange the api_key and persist auth.
        print("Waiting for authentication callback...")
        try:
            page.wait_for_url(f"{public_url}/**", timeout=30000)
        except Exception:
            pass

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not auth_file_is_fresh(started_at):
            page.wait_for_timeout(1000)

        if not auth_file_is_fresh(started_at):
            print()
            print("Debug — final URL:")
            print(f"  {page.url}")
            print("Debug — cookies found:")
            for cookie in page.context.cookies():
                print(f"  {cookie['name']}: {cookie['value'][:40]}...")

        browser.close()

    if not auth_file_is_fresh(started_at):
        print()
        print("Error: GTS callback did not write a fresh access token")
        print("Check the final URL/debug output above and rerun `just t3k-auth`.")
        sys.exit(1)

    print()
    print(f"Login successful. Auth saved to {AUTH_FILE}")


if __name__ == "__main__":
    main()
