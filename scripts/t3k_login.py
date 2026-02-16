#!/usr/bin/env python3
"""T3K Login — headless Chromium magic-link authentication.

Usage: just t3k-login

Launches headless Chromium, navigates to T3K login page, fills email,
prompts for 6-digit code, completes auth, saves encrypted tokens to
.gts-auth.json.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Auth file at worktree root (parent of any worktree dir)
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
AUTH_FILE = WORKTREE_ROOT / ".gts-auth.json"
LOGIN_EMAIL = "brewsterbear@gmail.com"
T3K_BASE_URL = "https://www.tone3000.com"


def get_encryption_key() -> str:
    """Load OAUTH_ENCRYPTION_KEY from .env file."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("OAUTH_ENCRYPTION_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if not key:
        print("Error: OAUTH_ENCRYPTION_KEY not found in .env or environment")
        sys.exit(1)
    return key


def main() -> None:
    """Run the T3K login flow."""
    try:
        from cryptography.fernet import Fernet
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install cryptography playwright")
        sys.exit(1)

    encryption_key = get_encryption_key()
    fernet = Fernet(encryption_key.encode())

    print(f"T3K Login — {LOGIN_EMAIL}")
    print(f"Auth file: {AUTH_FILE}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page()

        # Navigate to T3K login
        print("Opening T3K login page...")
        page.goto(f"{T3K_BASE_URL}/login", wait_until="networkidle")

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
        code = input("Enter 6-digit code from email: ").strip()
        if len(code) != 6 or not code.isdigit():
            print("Error: Expected 6-digit numeric code")
            browser.close()
            sys.exit(1)

        # Fill code
        code_input = page.locator('input[name="code"], input[type="text"]')
        code_input.fill(code)

        # Submit code
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()

        # Wait for redirect / auth completion
        print("Waiting for authentication...")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Extract tokens from cookies/storage
        cookies = page.context.cookies()
        access_token = None
        refresh_token = None

        for cookie in cookies:
            if not access_token and (
                "access" in cookie["name"].lower() or "token" in cookie["name"].lower()
            ):
                access_token = cookie["value"]
            if "refresh" in cookie["name"].lower():
                refresh_token = cookie["value"]

        # Also check localStorage
        if not access_token:
            access_token = page.evaluate(
                "() => localStorage.getItem('access_token') || sessionStorage.getItem('access_token')"
            )
        if not refresh_token:
            refresh_token = page.evaluate(
                "() => localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token')"
            )

        browser.close()

        if not access_token:
            print("Error: Could not extract access token from browser session")
            print("The login flow may have changed. Check T3K manually.")
            sys.exit(1)

        # Encrypt and save
        auth_data = {}
        if AUTH_FILE.exists():
            import contextlib

            with contextlib.suppress(json.JSONDecodeError):
                auth_data = json.loads(AUTH_FILE.read_text())

        auth_data["access_token"] = fernet.encrypt(access_token.encode()).decode()
        if refresh_token:
            auth_data["refresh_token"] = fernet.encrypt(refresh_token.encode()).decode()
        auth_data["expires_at"] = None  # Unknown — refresh job will determine
        auth_data["auth_status"] = "valid"
        auth_data["saved_at"] = datetime.now(UTC).isoformat()

        AUTH_FILE.write_text(json.dumps(auth_data, indent=2))
        os.chmod(AUTH_FILE, 0o600)

        print()
        print(f"Login successful. Auth saved to {AUTH_FILE}")


if __name__ == "__main__":
    main()
