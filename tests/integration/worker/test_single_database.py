"""Integration tests for single-database worker wiring."""

from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.integration
class TestSingleDatabase:
    """Worker core and T3K sessions should resolve to the same database."""

    async def test_core_and_t3k_sessions_share_database(self) -> None:
        from worker.db import get_core_session, get_t3k_session

        async with get_core_session() as core_session, get_t3k_session() as t3k_session:
            core_db = await core_session.execute(text("SELECT current_database()"))
            t3k_db = await t3k_session.execute(text("SELECT current_database()"))

            assert core_db.scalar_one() == "gts_core"
            assert t3k_db.scalar_one() == "gts_core"

    async def test_t3k_tables_queryable_from_core_session(self) -> None:
        from worker.db import get_core_session

        async with get_core_session() as session:
            result = await session.execute(text("SELECT to_regclass('public.t3k_tones_staging')"))
            assert result.scalar_one() == "t3k_tones_staging"

    async def test_t3k_tables_queryable_from_t3k_session(self) -> None:
        from worker.db import get_t3k_session

        async with get_t3k_session() as session:
            result = await session.execute(text("SELECT to_regclass('public.t3k_models_staging')"))
            assert result.scalar_one() == "t3k_models_staging"
