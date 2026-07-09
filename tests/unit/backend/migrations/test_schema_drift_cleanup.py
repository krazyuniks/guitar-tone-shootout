"""Regression coverage for the schema-drift cleanup work unit."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.schema import CreateSchema, DropSchema

from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import AudioSegment, Shootout

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Connection
    from sqlalchemy.engine import Engine

ALEMBIC_INI = Path("infrastructure/migrations/alembic.ini")


def _sync_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.fail("DATABASE_URL environment variable is required for migration drift tests")
    return database_url.replace("+asyncpg", "")


@pytest.fixture
def migrated_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """Run the Alembic chain to head in an isolated PostgreSQL schema."""
    database_url = _sync_database_url()
    schema = f"schema_drift_cleanup_{uuid.uuid4().hex}"
    admin_engine = create_engine(database_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        connection.execute(CreateSchema(schema))

    version_metadata = MetaData(schema=schema)
    Table("alembic_version", version_metadata, Column("version_num", String(32), nullable=False))
    version_metadata.create_all(admin_engine)

    search_path = schema
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={search_path}")
    command.upgrade(Config(ALEMBIC_INI), "head")

    engine = create_engine(database_url, connect_args={"options": f"-csearch_path={search_path}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        admin_engine.dispose()


def test_job_model_does_not_map_dead_taskiq_columns() -> None:
    """TaskIQ-era job columns are not part of the ORM shape."""
    columns = set(Job.__table__.columns.keys())
    indexes = {index.name for index in Job.__table__.indexes}

    assert "task_id" not in columns
    assert "depends_on" not in columns
    assert "ix_jobs_task_id" not in indexes


def test_shootout_model_does_not_store_video_projection_state() -> None:
    """Video state is projected from the video BC, not stored on shootouts."""
    columns = set(Shootout.__table__.columns.keys())

    assert "video_status" not in columns
    assert "video_job_id" not in columns


def test_audio_segment_model_records_sample_rate() -> None:
    """Montage assembly can rely on each segment carrying its sample rate."""
    columns = AudioSegment.__table__.columns

    assert "sample_rate" in columns
    assert columns["sample_rate"].nullable is False


def _columns(connection: Connection, table_name: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table_name)}


def _assert_column_matches_orm(
    reflected_column: dict[str, object],
    orm_column_name: str,
    orm_column_nullable: bool,
    orm_column_has_server_default: bool,
) -> None:
    assert reflected_column["nullable"] is orm_column_nullable
    assert (reflected_column["default"] is not None) is orm_column_has_server_default, (
        f"{orm_column_name} server default drifted: {reflected_column['default']!r}"
    )


def test_upgrade_head_schema_matches_cleanup_metadata(migrated_engine: Engine) -> None:
    """The upgraded database shape matches ORM metadata for cleaned schema drift."""
    with migrated_engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())

        assert {"core_users", "core_jobs", "core_shootouts", "core_audio_segments"} <= tables
        assert {"users", "jobs", "shootouts", "audio_segments"}.isdisjoint(tables)

        job_columns = _columns(connection, Job.__tablename__)
        shootout_columns = _columns(connection, Shootout.__tablename__)
        audio_segment_columns = _columns(connection, AudioSegment.__tablename__)
        job_indexes = {index["name"] for index in inspector.get_indexes(Job.__tablename__)}

        assert "depends_on" not in job_columns
        assert "task_id" not in job_columns
        assert "ix_jobs_task_id" not in job_indexes
        assert "video_status" not in shootout_columns
        assert "video_job_id" not in shootout_columns

        assert "sample_rate" in audio_segment_columns
        _assert_column_matches_orm(
            audio_segment_columns["sample_rate"],
            "core_audio_segments.sample_rate",
            AudioSegment.__table__.columns["sample_rate"].nullable,
            AudioSegment.__table__.columns["sample_rate"].server_default is not None,
        )
        _assert_column_matches_orm(
            job_columns["max_attempts"],
            "core_jobs.max_attempts",
            Job.__table__.columns["max_attempts"].nullable,
            Job.__table__.columns["max_attempts"].server_default is not None,
        )
