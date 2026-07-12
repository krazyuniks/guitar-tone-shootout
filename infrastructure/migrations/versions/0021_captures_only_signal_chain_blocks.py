"""Reduce signal chain blocks to captured gear references.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("core_presets")
    op.drop_column("core_signal_chain_blocks", "block_type_id")
    op.drop_column("core_signal_chain_blocks", "params")
    op.execute(
        sa.text(
            "DELETE FROM core_signal_chain_blocks "
            "WHERE user_gear_id IS NULL OR gear_type IS NULL"
        )
    )
    op.alter_column("core_signal_chain_blocks", "user_gear_id", nullable=False)
    op.alter_column("core_signal_chain_blocks", "gear_type", nullable=False)
    op.drop_table("core_block_types")


def downgrade() -> None:
    op.create_table(
        "core_block_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_params", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id", name="pk_block_types"),
        sa.UniqueConstraint("name", name="uq_block_types_name"),
    )
    op.alter_column("core_signal_chain_blocks", "gear_type", nullable=True)
    op.alter_column("core_signal_chain_blocks", "user_gear_id", nullable=True)
    op.add_column(
        "core_signal_chain_blocks",
        sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "core_signal_chain_blocks",
        sa.Column("block_type_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_signal_chain_blocks_block_type_id_block_types",
        "core_signal_chain_blocks",
        "core_block_types",
        ["block_type_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "core_presets",
        sa.Column("signal_chain_block_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_chain_block_id"],
            ["core_signal_chain_blocks.id"],
            name="fk_presets_signal_chain_block_id_signal_chain_blocks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_presets"),
    )
    op.create_index("ix_presets_block_id", "core_presets", ["signal_chain_block_id"])
