"""Create msg_consumer_offsets table for event consumption tracking.

Revision ID: 0017
Revises: 0016
Create Date: 2026-02-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "msg_consumer_offsets",
        sa.Column("consumer_id", sa.Text(), nullable=False),
        sa.Column("queue_name", sa.Text(), nullable=False),
        sa.Column("last_processed_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("consumer_id", "queue_name"),
    )


def downgrade() -> None:
    op.drop_table("msg_consumer_offsets")
