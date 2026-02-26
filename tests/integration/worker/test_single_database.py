"""Integration tests for single-database worker wiring."""

from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.integration
class TestSingleDatabase:
    """Worker session resolves to the single gts_core database."""

    async def test_core_session_connects_to_gts_core(self) -> None:
        from worker.db import get_core_session

        async with get_core_session() as session:
            db = await session.execute(text("SELECT current_database()"))
            assert db.scalar_one() == "gts_core"

    async def test_t3k_tables_queryable_from_core_session(self) -> None:
        from worker.db import get_core_session

        async with get_core_session() as session:
            result = await session.execute(text("SELECT to_regclass('public.t3k_tones_staging')"))
            assert result.scalar_one() == "t3k_tones_staging"
