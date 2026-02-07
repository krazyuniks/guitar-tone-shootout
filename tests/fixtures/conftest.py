"""Fixtures configuration for query counter tests.

Monkey-patches AsyncSession to make expire_all() awaitable for test compatibility.
Enables SQLite foreign keys for proper CASCADE behavior.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy.pool.base import _ConnectionFairy


@pytest.fixture(autouse=True)
async def _enable_sqlite_foreign_keys(db_engine) -> None:  # type: ignore[no-untyped-def]
    """Enable foreign key constraints for SQLite engines.

    SQLite requires 'PRAGMA foreign_keys=ON' to enforce foreign key constraints
    and ON DELETE CASCADE behavior. Without this, even though the schema defines
    ON DELETE CASCADE, SQLite won't use it and SQLAlchemy will issue SELECT
    queries to manually cascade deletes.

    This fixture executes the PRAGMA on the existing connection pool.
    """
    from sqlalchemy import text

    # Execute PRAGMA on the current connection
    async with db_engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture(autouse=True)
def _patch_async_session_expire_all() -> None:
    """Patch AsyncSession.expire_all() to be awaitable and preserve PKs.

    The test file incorrectly uses 'await db_session.expire_all()' but
    expire_all() is a synchronous method. This patch:
    1. Makes it return an awaitable for test compatibility
    2. Preserves primary key values in instance state to avoid lazy loading
    """
    from sqlalchemy import inspect as sa_inspect

    original_expire_all = AsyncSession.expire_all

    async def async_expire_all(self: AsyncSession) -> None:
        """Async wrapper for expire_all() that preserves primary keys."""
        # Store all primary key values from instance state before expiring
        pk_values = {}
        for instance in list(self.identity_map.values()):
            state = sa_inspect(instance)
            mapper = state.mapper
            pk_attrs = [col.key for col in mapper.primary_key]
            # Get PK values directly from dict without triggering loads
            pk_values[instance] = {
                attr: state.dict.get(attr)
                for attr in pk_attrs
                if attr in state.dict
            }

        # Expire all attributes
        original_expire_all(self)

        # Restore primary key values directly to instance dict
        for instance, pks in pk_values.items():
            state = sa_inspect(instance)
            for attr, value in pks.items():
                if value is not None:
                    state.dict[attr] = value

    # Monkey-patch the method
    AsyncSession.expire_all = async_expire_all  # type: ignore[method-assign]

    yield

    # Restore original method
    AsyncSession.expire_all = original_expire_all  # type: ignore[method-assign]
