"""Add group_id column to signal_chains table.

Links signal chains to their optional signal chain group.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signal_chains",
        sa.Column("group_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_signal_chains_group_id",
        "signal_chains",
        "signal_chain_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_signal_chains_group_id", "signal_chains", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_chains_group_id", table_name="signal_chains")
    op.drop_constraint("fk_signal_chains_group_id", "signal_chains", type_="foreignkey")
    op.drop_column("signal_chains", "group_id")
