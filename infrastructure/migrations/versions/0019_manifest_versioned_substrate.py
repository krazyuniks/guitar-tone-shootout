"""Manifest table and the versioned render substrate (ADR-0004).

core_shootout_manifests holds the immutable, versioned render-time snapshot;
Shootout.render_version and AudioSegment.version are the versioned substrate
the finalise and idempotent-consume paths key on. Existing duplicate segments
(the pre-fix redelivery shape) are numbered by insertion order before the
unique constraint lands, so the adversarial shape migrates instead of failing.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "core_shootout_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "shootout_id",
            sa.Uuid(),
            sa.ForeignKey("core_shootouts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "shootout_id", "version", name="uq_shootout_manifests_shootout_version"
        ),
    )

    op.add_column(
        "core_shootouts",
        sa.Column("render_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "core_audio_segments",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Adversarial shape: pre-fix redelivery inserted duplicate segments per
    # chain with nothing to prevent it. Number duplicates by insertion order
    # (UUIDv7 primary keys are time-ordered) so the unique constraint can land
    # without data loss; the newest duplicate gets the highest version.
    op.execute(
        """
        WITH numbered AS (
            SELECT id, row_number() OVER (
                PARTITION BY shootout_chain_id ORDER BY id
            ) AS rn
            FROM core_audio_segments
        )
        UPDATE core_audio_segments s
        SET version = n.rn
        FROM numbered n
        WHERE s.id = n.id AND n.rn > 1
        """
    )
    # Align each shootout's render_version with its highest COMPLETE version:
    # the largest v every chain has a segment for. Per-chain versions are
    # contiguous 1..n (row_number above), so that is min over chains of the
    # per-chain max - never the global max, which a single chain's duplicates
    # would push past versions other chains do not have.
    op.execute(
        """
        UPDATE core_shootouts sh
        SET render_version = sub.complete_version
        FROM (
            SELECT sc.shootout_id, min(cmax.maxv) AS complete_version
            FROM (
                SELECT shootout_chain_id, max(version) AS maxv
                FROM core_audio_segments
                GROUP BY shootout_chain_id
            ) cmax
            JOIN core_shootout_chains sc ON sc.id = cmax.shootout_chain_id
            GROUP BY sc.shootout_id
        ) sub
        WHERE sh.id = sub.shootout_id AND sub.complete_version > 1
        """
    )

    op.create_unique_constraint(
        "uq_audio_segments_chain_version",
        "core_audio_segments",
        ["shootout_chain_id", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_audio_segments_chain_version", "core_audio_segments", type_="unique")
    op.drop_column("core_audio_segments", "version")
    op.drop_column("core_shootouts", "render_version")
    op.drop_table("core_shootout_manifests")
