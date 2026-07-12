"""Add shootout visibility independently of processing status.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "core_shootouts",
        sa.Column("visibility", sa.String(length=50), nullable=False, server_default="public"),
    )
    op.create_index("ix_shootouts_visibility", "core_shootouts", ["visibility"])
    op.create_check_constraint(
        "ck_shootouts_visibility",
        "core_shootouts",
        "visibility IN ('public', 'unlisted', 'private')",
    )
def downgrade() -> None:
    op.drop_constraint("ck_shootouts_visibility", "core_shootouts", type_="check")
    op.drop_index("ix_shootouts_visibility", table_name="core_shootouts")
    op.drop_column("core_shootouts", "visibility")
