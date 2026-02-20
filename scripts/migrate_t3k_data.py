#!/usr/bin/env -S python3 -u
"""Copy T3K data from gts_t3k_source into gts_core t3k_* tables.

The script is idempotent:
- Inserts use ON CONFLICT DO NOTHING.
- Completed steps are tracked in t3k_data_migration_checkpoints.
- Re-running skips completed steps unless --force is provided.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.engine.url import make_url

LOGGER = logging.getLogger("migrate_t3k_data")
CHECKPOINT_TABLE = "t3k_data_migration_checkpoints"
StepHandler = Callable[[Engine, Engine, int], int]


@dataclass(frozen=True)
class MigrationStep:
    key: str
    description: str


def _to_sync_url(database_url: str) -> str:
    return database_url.replace("+asyncpg", "")


def _default_source_url(core_url: str) -> str:
    parsed = make_url(core_url)
    return str(parsed.set(database="gts_t3k_source"))


def _build_urls() -> tuple[str, str]:
    core_url = os.getenv("DATABASE_URL")
    if not core_url:
        raise RuntimeError("DATABASE_URL is required")

    source_url = os.getenv("T3K_DATABASE_URL") or os.getenv("T3K_SOURCE_DATABASE_URL")
    if not source_url:
        source_url = _default_source_url(core_url)

    return _to_sync_url(core_url), _to_sync_url(source_url)


def _create_checkpoint_table(target: Engine) -> None:
    with target.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {CHECKPOINT_TABLE} (
                    checkpoint_key TEXT PRIMARY KEY,
                    rows_copied BIGINT NOT NULL,
                    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )


def _checkpoint_exists(target: Engine, key: str) -> bool:
    with target.connect() as conn:
        result = conn.execute(
            text(f"SELECT 1 FROM {CHECKPOINT_TABLE} WHERE checkpoint_key = :key"),
            {"key": key},
        )
        return result.scalar_one_or_none() is not None


def _write_checkpoint(target: Engine, key: str, rows_copied: int) -> None:
    with target.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO {CHECKPOINT_TABLE} (checkpoint_key, rows_copied, completed_at)
                VALUES (:key, :rows_copied, NOW())
                ON CONFLICT (checkpoint_key)
                DO UPDATE SET rows_copied = EXCLUDED.rows_copied, completed_at = EXCLUDED.completed_at
                """
            ),
            {"key": key, "rows_copied": rows_copied},
        )


def _column_exists(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
        return result.scalar_one_or_none() is not None


def _fetch_batches(source: Engine, query: str, batch_size: int) -> Iterator[list[RowMapping]]:
    with source.connect() as conn:
        result = conn.execution_options(stream_results=True).execute(text(query))
        while True:
            batch = result.mappings().fetchmany(batch_size)
            if not batch:
                break
            yield batch


def _build_insert_sql(table: str, columns: list[str], conflict_columns: list[str]) -> str:
    col_sql = ", ".join(columns)
    bind_sql = ", ".join(f":{col}" for col in columns)
    conflict_sql = ", ".join(conflict_columns)
    return (
        f"INSERT INTO {table} ({col_sql}) VALUES ({bind_sql}) "
        f"ON CONFLICT ({conflict_sql}) DO NOTHING RETURNING 1"
    )


def _insert_rows(
    target: Engine,
    table: str,
    rows: list[dict],
    *,
    conflict_columns: list[str],
) -> int:
    if not rows:
        return 0

    insert_sql = text(_build_insert_sql(table, list(rows[0].keys()), conflict_columns))
    inserted = 0
    with target.begin() as conn:
        for row in rows:
            if conn.execute(insert_sql, row).scalar_one_or_none() is not None:
                inserted += 1
    return inserted


def _step_copy_creators(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        """
        SELECT id, username, avatar_url, bio, url
        FROM t3k_users_staging
        ORDER BY id
        """,
        batch_size,
    ):
        rows = [dict(row) for row in batch]
        total += _insert_rows(target, "t3k_creators", rows, conflict_columns=["id"])
    return total


def _step_copy_packs(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        """
        SELECT
            id,
            title,
            description,
            tags,
            makes,
            gear,
            platform,
            models_count,
            favorites_count,
            downloads_count,
            images,
            user_id,
            url,
            created_at,
            updated_at,
            last_synced_at
        FROM t3k_tones_staging
        ORDER BY id
        """,
        batch_size,
    ):
        rows = [dict(row) for row in batch]
        total += _insert_rows(target, "t3k_packs", rows, conflict_columns=["id"])
    return total


def _step_copy_models(source: Engine, target: Engine, batch_size: int) -> int:
    has_file_synced_at = _column_exists(source, "t3k_models_staging", "file_synced_at")
    file_synced_at_sql = (
        "file_synced_at" if has_file_synced_at else "NULL::timestamptz AS file_synced_at"
    )

    total = 0
    for batch in _fetch_batches(
        source,
        f"""
        SELECT
            id,
            tone_id,
            user_id,
            name,
            model_url,
            size,
            created_at,
            updated_at,
            {file_synced_at_sql}
        FROM t3k_models_staging
        ORDER BY id
        """,
        batch_size,
    ):
        rows = [dict(row) for row in batch]
        total += _insert_rows(target, "t3k_models", rows, conflict_columns=["id"])
    return total


def _step_copy_sync_checkpoints(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        """
        SELECT source_name, entity_type, last_synced_at, last_record_id, total_synced
        FROM sync_checkpoints
        ORDER BY source_name, entity_type
        """,
        batch_size,
    ):
        rows = [dict(row) for row in batch]
        total += _insert_rows(
            target,
            "t3k_sync_checkpoints",
            rows,
            conflict_columns=["source_name", "entity_type"],
        )
    return total


def _step_copy_tags(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        "SELECT id AS pack_id, tags FROM t3k_tones_staging ORDER BY id",
        batch_size,
    ):
        rows: list[dict] = []
        for row in batch:
            for tag in row["tags"] or []:
                cleaned = str(tag).strip()
                if cleaned:
                    rows.append({"pack_id": row["pack_id"], "name": cleaned})
        total += _insert_rows(target, "t3k_tags", rows, conflict_columns=["pack_id", "name"])
    return total


def _step_copy_makes(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        "SELECT id AS pack_id, makes FROM t3k_tones_staging ORDER BY id",
        batch_size,
    ):
        rows: list[dict] = []
        for row in batch:
            for make in row["makes"] or []:
                cleaned = str(make).strip()
                if cleaned:
                    rows.append({"pack_id": row["pack_id"], "name": cleaned})
        total += _insert_rows(target, "t3k_makes", rows, conflict_columns=["pack_id", "name"])
    return total


def _step_copy_pack_images(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        "SELECT id AS pack_id, images FROM t3k_tones_staging ORDER BY id",
        batch_size,
    ):
        rows: list[dict] = []
        for row in batch:
            for index, image_url in enumerate(row["images"] or []):
                cleaned = str(image_url).strip()
                if cleaned:
                    rows.append(
                        {
                            "pack_id": row["pack_id"],
                            "url": cleaned,
                            "position": index,
                        }
                    )
        total += _insert_rows(
            target,
            "t3k_pack_images",
            rows,
            conflict_columns=["pack_id", "url"],
        )
    return total


def _step_copy_pack_links(source: Engine, target: Engine, batch_size: int) -> int:
    total = 0
    for batch in _fetch_batches(
        source,
        "SELECT id AS pack_id, url FROM t3k_tones_staging ORDER BY id",
        batch_size,
    ):
        rows: list[dict] = []
        for row in batch:
            url = str(row["url"] or "").strip()
            if url:
                rows.append({"pack_id": row["pack_id"], "url": url, "link_type": "tone"})
        total += _insert_rows(target, "t3k_pack_links", rows, conflict_columns=["pack_id", "url"])
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate T3K data into gts_core.t3k_* tables")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows fetched per batch")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run all steps even if checkpoint exists",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    core_url, source_url = _build_urls()
    LOGGER.info("Target (core) URL: %s", core_url)
    LOGGER.info("Source (t3k) URL: %s", source_url)

    source_engine = create_engine(source_url)
    target_engine = create_engine(core_url)

    _create_checkpoint_table(target_engine)

    steps: list[tuple[MigrationStep, StepHandler]] = [
        (MigrationStep("copy_creators", "Copy creators"), _step_copy_creators),
        (MigrationStep("copy_packs", "Copy packs"), _step_copy_packs),
        (MigrationStep("copy_models", "Copy models"), _step_copy_models),
        (
            MigrationStep("copy_sync_checkpoints", "Copy sync checkpoints"),
            _step_copy_sync_checkpoints,
        ),
        (MigrationStep("copy_tags", "Copy tags"), _step_copy_tags),
        (MigrationStep("copy_makes", "Copy makes"), _step_copy_makes),
        (MigrationStep("copy_pack_images", "Copy pack images"), _step_copy_pack_images),
        (MigrationStep("copy_pack_links", "Copy pack links"), _step_copy_pack_links),
    ]

    try:
        for step, handler in steps:
            if not args.force and _checkpoint_exists(target_engine, step.key):
                LOGGER.info("Skipping %-24s (checkpoint exists)", step.key)
                continue

            LOGGER.info("Running %-24s %s", step.key, step.description)
            copied = handler(source_engine, target_engine, args.batch_size)
            _write_checkpoint(target_engine, step.key, copied)
            LOGGER.info("Completed %-22s rows_copied=%d", step.key, copied)
    finally:
        source_engine.dispose()
        target_engine.dispose()

    LOGGER.info("Migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
