"""Regression coverage for the schema-drift cleanup work unit."""

from __future__ import annotations

from pathlib import Path

from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import AudioSegment, Shootout

BASELINE = Path("infrastructure/migrations/versions/0001_baseline.py")


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


def test_baseline_uses_core_prefixed_tables_for_core_orm() -> None:
    """The squashed baseline creates the same core_* table labels the ORM maps."""
    source = BASELINE.read_text()

    assert 'op.create_table(\n        "core_users",' in source
    assert 'op.create_table(\n        "core_jobs",' in source
    assert 'op.create_table(\n        "core_shootouts",' in source
    assert 'op.create_table(\n        "core_audio_segments",' in source
    assert 'op.create_table(\n        "users",' not in source
    assert 'op.create_table(\n        "jobs",' not in source
    assert 'op.create_table(\n        "shootouts",' not in source
    assert 'op.create_table(\n        "audio_segments",' not in source


def test_baseline_matches_named_schema_cleanup() -> None:
    """The baseline owns the cleaned current shape for the named columns."""
    source = BASELINE.read_text()

    assert 'sa.Column("sample_rate", sa.Integer(), nullable=False)' in source
    assert 'sa.Column("depends_on"' not in source
    assert 'sa.Column("task_id"' not in source
    assert 'sa.Column("video_status"' not in source
    assert 'sa.Column("video_job_id"' not in source
    assert 'op.create_index("ix_jobs_task_id"' not in source
