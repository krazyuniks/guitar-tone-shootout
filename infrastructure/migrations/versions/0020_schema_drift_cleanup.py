"""Clean up schema drift from the core ORM.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if _index_exists("core_jobs", "ix_jobs_task_id"):
        op.drop_index("ix_jobs_task_id", table_name="core_jobs")

    for column_name in ("task_id", "depends_on"):
        if _column_exists("core_jobs", column_name):
            op.drop_column("core_jobs", column_name)

    for column_name in ("video_job_id", "video_status"):
        if _column_exists("core_shootouts", column_name):
            op.drop_column("core_shootouts", column_name)

    if not _column_exists("core_audio_segments", "sample_rate"):
        op.add_column(
            "core_audio_segments",
            sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="44100"),
        )
        op.alter_column("core_audio_segments", "sample_rate", server_default=None)


def downgrade() -> None:
    if _column_exists("core_audio_segments", "sample_rate"):
        op.drop_column("core_audio_segments", "sample_rate")

    if not _column_exists("core_shootouts", "video_status"):
        op.add_column("core_shootouts", sa.Column("video_status", sa.String(50), nullable=True))
    if not _column_exists("core_shootouts", "video_job_id"):
        op.add_column("core_shootouts", sa.Column("video_job_id", sa.String(255), nullable=True))

    if not _column_exists("core_jobs", "depends_on"):
        op.add_column(
            "core_jobs",
            sa.Column("depends_on", sa.JSON(), nullable=False, server_default="[]"),
        )
        op.alter_column("core_jobs", "depends_on", server_default=None)
    if not _column_exists("core_jobs", "task_id"):
        op.add_column("core_jobs", sa.Column("task_id", sa.String(100), nullable=True))
    if not _index_exists("core_jobs", "ix_jobs_task_id"):
        op.create_index("ix_jobs_task_id", "core_jobs", ["task_id"])
