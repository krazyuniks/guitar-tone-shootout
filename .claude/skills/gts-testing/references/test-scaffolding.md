# Test Scaffolding Patterns

Quick-start patterns for common GTS test scenarios. Extracted from production-proven templates.

## Unit/Integration Test with PostgreSQL (ORM Models)

Use the shared `session` fixture from `tests/conftest.py`. No inline engine or session setup needed — SQLite is banned.

```python
"""Tests for SomeModel."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.some_model import SomeModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestSomeModel:
    async def test_creation(self, session: AsyncSession) -> None:
        obj = SomeModel(name="test")
        session.add(obj)
        await session.commit()

        result = await session.execute(select(SomeModel))
        saved = result.scalar_one()
        assert saved.name == "test"
```

The `session` fixture (alias for `db_session`) provides SAVEPOINT isolation — all changes are rolled back after each test. No teardown code needed.

## Verifying a Module/Class Exists

Just import it. If the file does not exist, pytest collection fails -- that IS the red phase. No special existence checks needed.

```python
from core.domain.value_objects.gear_type import GearType

def test_gear_type_has_expected_values():
    assert GearType.AMP.value == "amp"
    assert GearType.PEDAL.value == "pedal"
```

## Verifying Enum Values

```python
from core.domain.value_objects.platform import Platform

def test_platform_enum_has_required_values():
    expected = {"nam", "ir", "aida_x"}
    actual = {p.value for p in Platform}
    assert expected.issubset(actual)
```

## Service Test with Real Repository (NOT Mock)

```python
"""Unit tests for SomeService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.repositories.some_repo import SomeRepository
from webapp.services.some_service import SomeService


@pytest.fixture
def service(session: AsyncSession) -> SomeService:
    repository = SomeRepository(session=session)
    return SomeService(repository=repository)


class TestSomeService:
    async def test_creates_entity(self, service: SomeService, session: AsyncSession) -> None:
        result = await service.create(name="test")
        assert result.name == "test"

        # Verify it persisted to the database
        from sqlalchemy import select
        from webapp.adapters.persistence.models.some_model import SomeModel
        stmt = select(SomeModel).where(SomeModel.name == "test")
        db_result = await session.execute(stmt)
        assert db_result.scalar_one() is not None
```

## E2E Test Pattern (Host-Only)

E2E tests go in `tests/e2e/python/tests/`. They run on HOST via `just test-golden-path`, NOT in Docker.

**CRITICAL: E2E tests CANNOT import internal packages.** The host does not have `webapp`, `core`, `audio`, etc. installed. Use raw SQL via `text()` for database queries:

```python
# CORRECT -- raw SQL for E2E database verification
from sqlalchemy import text
result = await db_session.execute(text("SELECT id, slug FROM gear WHERE is_public = true LIMIT 1"))

# BANNED -- internal packages not available on host
from webapp.adapters.persistence.models.gear import Gear  # ModuleNotFoundError
from core.domain.entities.user import User                # ModuleNotFoundError
```
