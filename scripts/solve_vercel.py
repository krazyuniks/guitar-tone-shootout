#!/usr/bin/env python3
"""Solve Vercel Security Checkpoint using Playwright on the host.

Visits tone3000.com in a headed Chromium browser, waits for the JS challenge
to complete, then saves cookies to .vercel-cookies.json so the worker
container can send them with API requests (same external IP).

Usage:
    just solve-vercel
    # or directly:
    cd tests/e2e/python && uv run python3 ../../../scripts/solve_vercel.py
"""

import json
import os
import sys
from pathlib import Path

# Cookie file lives next to .gts-auth.json in the worktrees parent dir
WORKTREES_DIR = Path(__file__).resolve().parent.parent.parent  # up from main/scripts/
COOKIE_FILE = WORKTREES_DIR / ".vercel-cookies.json"
TARGET_URL = "https://www.tone3000.com"


def main() -> None:
    from playwright.sync_api import sync_playwright

    print(f"Solving Vercel challenge for {TARGET_URL}")
    print(f"Cookie file: {COOKIE_FILE}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.environ.get(
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium"
            ),
            args=["--no-sandbox", "--disable-gpu"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print("Navigating to tone3000.com...")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)

        # Check if we hit the challenge page
        content = page.content()
        if "Vercel Security Checkpoint" in content:
            print("Challenge page detected — waiting for JS to solve it...")
            # Wait for the page to navigate away from the challenge
            page.wait_for_function(
                "!document.body.innerText.includes('Vercel Security Checkpoint')",
                timeout=30_000,
            )
            print("Challenge solved!")
        else:
            print("No challenge page — site loaded directly")

        # Extract cookies
        cookies = context.cookies()
        vercel_cookies = [
            {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]}
            for c in cookies
        ]

        browser.close()

    if not vercel_cookies:
        print("WARNING: No cookies extracted", file=sys.stderr)
        sys.exit(1)

    COOKIE_FILE.write_text(json.dumps(vercel_cookies, indent=2))
    os.chmod(COOKIE_FILE, 0o600)
    print(f"Saved {len(vercel_cookies)} cookies to {COOKIE_FILE}")

    # Show what we got
    for c in vercel_cookies:
        print(f"  {c['name']}={c['value'][:30]}... (domain={c['domain']})")


if __name__ == "__main__":
    main()
