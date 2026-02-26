#!/usr/bin/env python3
"""T3K Login — headless Chromium magic-link authentication.

Usage: just t3k-login

Launches headless Chromium, navigates to T3K login page, fills email,
prompts for 6-digit code, completes auth, saves encrypted tokens to
.gts-auth.json.

Token extraction: intercepts API responses during the login flow to capture
the access_token and refresh_token directly from the auth endpoint response.
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
        print("Install: uv sync --group host")
        sys.exit(1)

    encryption_key = get_encryption_key()
    fernet = Fernet(encryption_key.encode())

    print(f"T3K Login — {LOGIN_EMAIL}")
    print(f"Auth file: {AUTH_FILE}")
    print()

    # Capture tokens from API responses during login
    captured_tokens: dict[str, str] = {}

    def handle_response(response):
        """Intercept API responses to capture auth tokens."""
        url = response.url
        if response.status not in range(200, 300):
            return
        # Look for auth-related API responses
        if "/api/" not in url or "/auth/" not in url:
            return
        try:
            body = response.json()
        except Exception:
            return
        if "access_token" in body:
            captured_tokens["access_token"] = body["access_token"]
            if "refresh_token" in body:
                captured_tokens["refresh_token"] = body["refresh_token"]
            if "expires_in" in body:
                captured_tokens["expires_in"] = body["expires_in"]
            print(f"  Captured tokens from {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page()
        page.on("response", handle_response)

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

        # Fill code — T3K uses 6 individual digit inputs
        for i, digit in enumerate(code):
            digit_input = page.get_by_role("textbox", name=f"Digit {i + 1} of 6")
            digit_input.fill(digit)

        # Submit code
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()

        # Wait for auth API response
        print("Waiting for authentication...")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Fallback: extract from Supabase auth cookie
        if "access_token" not in captured_tokens:
            print("  No tokens captured from API responses, checking Supabase cookie...")
            from urllib.parse import unquote

            cookies = page.context.cookies()

            # Newer Supabase JS clients chunk the auth token across multiple cookies:
            # sb-<project>-auth-token.0, sb-<project>-auth-token.1, ...
            # Collect and reassemble chunks before attempting single-cookie parse.
            sb_chunks: dict[str, dict[int, str]] = {}
            for cookie in cookies:
                name = cookie["name"]
                if name.startswith("sb-") and "-auth-token." in name:
                    parts = name.rsplit(".", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        base, idx = parts[0], int(parts[1])
                        sb_chunks.setdefault(base, {})[idx] = cookie["value"]

            for base, chunks in sb_chunks.items():
                try:
                    full_value = "".join(chunks[i] for i in sorted(chunks))
                    token_data = json.loads(unquote(full_value))
                    if "access_token" in token_data:
                        captured_tokens["access_token"] = token_data["access_token"]
                        print(f"  Extracted access_token from chunked cookie: {base}.*")
                    if "refresh_token" in token_data:
                        captured_tokens["refresh_token"] = token_data["refresh_token"]
                        print(f"  Extracted refresh_token from chunked cookie: {base}.*")
                    if "expires_in" in token_data:
                        captured_tokens["expires_in"] = token_data["expires_in"]
                    elif "expires_at" in token_data:
                        remaining = int(token_data["expires_at"]) - int(time.time())
                        if remaining > 0:
                            captured_tokens["expires_in"] = str(remaining)
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue

            # Legacy: single un-chunked sb-*-auth-token cookie (older Supabase versions)
            if "access_token" not in captured_tokens:
                for cookie in cookies:
                    if cookie["name"].startswith("sb-") and cookie["name"].endswith("-auth-token"):
                        try:
                            token_data = json.loads(unquote(cookie["value"]))
                            if "access_token" in token_data:
                                captured_tokens["access_token"] = token_data["access_token"]
                                print(f"  Extracted access_token from cookie: {cookie['name']}")
                            if "refresh_token" in token_data:
                                captured_tokens["refresh_token"] = token_data["refresh_token"]
                                print(f"  Extracted refresh_token from cookie: {cookie['name']}")
                            if "expires_in" in token_data:
                                captured_tokens["expires_in"] = token_data["expires_in"]
                            elif "expires_at" in token_data:
                                # Supabase uses epoch seconds for expires_at
                                remaining = int(token_data["expires_at"]) - int(time.time())
                                if remaining > 0:
                                    captured_tokens["expires_in"] = str(remaining)
                        except (json.JSONDecodeError, ValueError):
                            continue

        # Debug: dump what we found if no tokens
        if "access_token" not in captured_tokens:
            print()
            print("Debug — cookies found:")
            for cookie in page.context.cookies():
                print(f"  {cookie['name']}: {cookie['value'][:40]}...")
            print("Debug — localStorage keys:")
            keys = page.evaluate("() => Object.keys(localStorage)")
            for k in keys:
                val = page.evaluate(f"() => localStorage.getItem('{k}')")
                print(f"  {k}: {val[:40] if val else '(empty)'}...")
            print("Debug — sessionStorage keys:")
            keys = page.evaluate("() => Object.keys(sessionStorage)")
            for k in keys:
                val = page.evaluate(f"() => sessionStorage.getItem('{k}')")
                print(f"  {k}: {val[:40] if val else '(empty)'}...")

        browser.close()

    access_token = captured_tokens.get("access_token")
    refresh_token = captured_tokens.get("refresh_token")
    expires_in = captured_tokens.get("expires_in")

    if not access_token:
        print()
        print("Error: Could not extract access token")
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
    if expires_in:
        expires_at = datetime.now(UTC).timestamp() + int(expires_in)
        auth_data["expires_at"] = datetime.fromtimestamp(expires_at, tz=UTC).isoformat()
    else:
        auth_data["expires_at"] = None
    auth_data["auth_status"] = "valid"
    auth_data["saved_at"] = datetime.now(UTC).isoformat()

    AUTH_FILE.write_text(json.dumps(auth_data, indent=2))
    os.chmod(AUTH_FILE, 0o600)

    print()
    print(f"Login successful. Auth saved to {AUTH_FILE}")
    if refresh_token:
        print("  Access token + refresh token captured")
    else:
        print("  Access token captured (no refresh token)")
    if expires_in:
        print(f"  Expires in {expires_in}s")


if __name__ == "__main__":
    main()
