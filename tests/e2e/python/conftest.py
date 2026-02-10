"""Shared pytest fixtures for E2E tests.

E2E tests are PURE browser tests — no database access allowed.
Database packages (sqlalchemy, asyncpg, psycopg) are not installed.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import async_playwright

if TYPE_CHECKING:
    import os
    from collections.abc import AsyncGenerator

    from playwright.async_api import Browser, Page

FORBIDDEN_MODULES = {"sqlalchemy", "asyncpg", "psycopg", "databases"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Block E2E tests from importing database packages."""
    for mod_name in list(sys.modules):
        if any(mod_name == f or mod_name.startswith(f"{f}.") for f in FORBIDDEN_MODULES):
            pytest.fail(
                f"E2E tests must not import database packages. Found: {mod_name}"
            )


@pytest.fixture
def frontend_url() -> str:
    """Base URL for the frontend (public-facing URL)."""
    import os

    return os.getenv("PUBLIC_URL", "https://localhost:9000")


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
    """Create an authenticated browser page.

    For now, this is the same as guest_page since the gear pages are public.
    When authentication is needed, this fixture will handle login.
    """
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await page.close()
    await context.close()
