"""Shared pytest fixtures for unit tests.

Provides a canonical ``test_user`` fixture that uses the ``session``
alias (backwards-compatible name for ``db_session``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user (canonical unit-test fixture).

    Uses ``session`` (the backwards-compatible alias for ``db_session``
    defined in the root conftest).
    """
    suffix = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"testuser_{suffix}",
        email=f"test_{suffix}@example.com",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
