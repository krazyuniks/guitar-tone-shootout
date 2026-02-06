"""Shared pytest fixtures for E2E tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from playwright.async_api import Browser, Page


@pytest.fixture(scope="session")
def frontend_url() -> str:
    """Base URL for the frontend."""
    return os.getenv("FRONTEND_URL", "http://localhost:9000")


@pytest.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a database engine for E2E test verification."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://gts:gts@localhost:5455/gts_core",
    )
    engine = create_async_engine(database_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for E2E test verification."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture(scope="session")
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
