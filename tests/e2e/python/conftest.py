"""Shared pytest fixtures for E2E tests.

E2E tests are PURE browser tests — no database access allowed.
Database packages (sqlalchemy, asyncpg, psycopg) are not installed.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from playwright.async_api import Browser, BrowserContext, Page

FORBIDDEN_MODULES = {"sqlalchemy", "asyncpg", "psycopg", "databases"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Block E2E tests from importing database packages."""
    for mod_name in list(sys.modules):
        if any(mod_name == f or mod_name.startswith(f"{f}.") for f in FORBIDDEN_MODULES):
            pytest.fail(f"E2E tests must not import database packages. Found: {mod_name}")


# --- URL fixtures ---


@pytest.fixture
def frontend_url() -> str:
    """Base URL for the frontend (public-facing URL via nginx)."""
    return os.getenv("E2E_BASE_URL", os.getenv("PUBLIC_URL", "https://localhost:9000"))


@pytest.fixture
def api_url() -> str:
    """Base URL for the webapp API (direct, bypasses nginx)."""
    webapp_port = os.getenv("WEBAPP_PORT", "8000")
    return os.getenv("E2E_API_URL", f"http://localhost:{webapp_port}")


# --- Browser fixtures ---


@pytest.fixture
async def browser() -> AsyncGenerator[Browser, None]:
    """Create a Playwright browser instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def guest_page(browser: Browser) -> AsyncGenerator[Page, None]:
    """Create an unauthenticated browser page."""
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await page.close()
    await context.close()


@pytest.fixture
async def page(browser: Browser) -> AsyncGenerator[Page, None]:
    """Create an unauthenticated browser page (alias for guest_page).

    Existing tests depend on this fixture name.
    """
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await page.close()
    await context.close()


# --- Auth fixtures (FAIL-not-skip semantics) ---


async def check_auth_status_or_fail(backend_url: str) -> dict:
    """Call GET /api/v1/auth/status on the backend.

    pytest.fail() (not skip) if auth is invalid or expired.
    Returns the auth status dict on success.
    """
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{backend_url}/api/v1/auth/status", timeout=10)
    except httpx.ConnectError:
        pytest.fail(
            f"Cannot connect to backend at {backend_url}. "
            "Is the webapp container running? Check: just up-d"
        )

    if resp.status_code != 200:
        pytest.fail(
            f"Auth status endpoint returned {resp.status_code}. "
            f"URL: {backend_url}/api/v1/auth/status"
        )

    data = resp.json()
    if not data.get("valid"):
        status = data.get("status", "unknown")
        username = data.get("username", "N/A")
        pytest.fail(
            f"Auth token is not valid (status={status}, username={username}). "
            "Run: ./worktree.py auth-login (on PC) then "
            "./worktree.py auth-restore (on server)"
        )

    return data


_verified_auth_cache: dict | None = None


@pytest.fixture
async def verified_auth() -> dict:
    """Auth verification gate — FAILS (not skips) if invalid.

    Caches the result so the HTTP call only happens once per session.
    """
    global _verified_auth_cache
    if _verified_auth_cache is not None:
        return _verified_auth_cache
    webapp_port = os.getenv("WEBAPP_PORT", "8000")
    backend_url = os.getenv("E2E_API_URL", f"http://localhost:{webapp_port}")
    _verified_auth_cache = await check_auth_status_or_fail(backend_url)
    return _verified_auth_cache


@pytest.fixture
async def auth_context(
    browser: Browser, verified_auth: dict, api_url: str
) -> AsyncGenerator[BrowserContext, None]:
    """Create an authenticated browser context.

    1. Calls POST /api/v1/auth/restore-session to get a JWT cookie
    2. Injects the gts_session cookie into a new browser context
    3. pytest.fail() on any auth failure
    """
    import httpx

    # Call restore-session to get JWT cookie
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_url}/api/v1/auth/restore-session",
                timeout=10,
            )
    except httpx.ConnectError:
        pytest.fail(f"Cannot connect to backend at {api_url}")

    if resp.status_code != 200:
        pytest.fail(
            f"restore-session returned {resp.status_code}: {resp.text}. "
            "Auth file may be missing. Run: ./worktree.py auth-restore"
        )

    # Extract gts_session cookie (NOT 'session' — archive had this bug)
    gts_cookie = None
    for cookie in resp.cookies.jar:
        if cookie.name == "gts_session":
            gts_cookie = cookie
            break

    if not gts_cookie:
        pytest.fail(
            "restore-session did not return gts_session cookie. "
            f"Response cookies: {[c.name for c in resp.cookies.jar]}"
        )

    # Determine the cookie domain for the frontend URL
    frontend_base = os.getenv("E2E_BASE_URL", os.getenv("PUBLIC_URL", "https://localhost:9000"))

    # Parse frontend URL to get domain for cookie
    from urllib.parse import urlparse

    parsed = urlparse(frontend_base)
    domain = parsed.hostname or "localhost"

    # Create browser context with the auth cookie
    context = await browser.new_context()
    await context.add_cookies(
        [
            {
                "name": "gts_session",
                "value": gts_cookie.value,
                "domain": domain,
                "path": "/",
                "httpOnly": True,
                "secure": parsed.scheme == "https",
                "sameSite": "Lax",
            }
        ]
    )

    yield context
    await context.close()


@pytest.fixture
async def auth_page(auth_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create an authenticated browser page."""
    page = await auth_context.new_page()
    yield page
    await page.close()
