"""Rename UserGear.gear_id to gear_model_id and update FK target.

Changes user_gear table to reference gear_models.id instead of gear.id:
- Drops old FK constraint (gear_id -> gear.id)
- Renames column gear_id to gear_model_id
- Creates new FK constraint (gear_model_id -> gear_models.id)
- Updates unique constraint from (user_id, gear_id) to (user_id, gear_model_id)
- Updates indexes to use gear_model_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename gear_id to gear_model_id and update FK to point to gear_models."""
    # Drop old constraints and indexes
    op.drop_constraint("uq_user_gear_user_gear", "user_gear", type_="unique")
    op.drop_index("ix_user_gear_gear_id", table_name="user_gear")
    op.drop_constraint("user_gear_gear_id_fkey", "user_gear", type_="foreignkey")

    # Rename column
    op.alter_column("user_gear", "gear_id", new_column_name="gear_model_id")

    # Create new FK constraint pointing to gear_models
    op.create_foreign_key(
        "user_gear_gear_model_id_fkey",
        "user_gear",
        "gear_models",
        ["gear_model_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create new unique constraint
    op.create_unique_constraint(
        "uq_user_gear_user_gear_model",
        "user_gear",
        ["user_id", "gear_model_id"],
    )

    # Create new index
    op.create_index("ix_user_gear_gear_model_id", "user_gear", ["gear_model_id"])


def downgrade() -> None:
    """Reverse changes: rename gear_model_id back to gear_id and restore FK to gear."""
    # Drop new constraints and indexes
    op.drop_constraint("uq_user_gear_user_gear_model", "user_gear", type_="unique")
    op.drop_index("ix_user_gear_gear_model_id", table_name="user_gear")
    op.drop_constraint("user_gear_gear_model_id_fkey", "user_gear", type_="foreignkey")

    # Rename column back
    op.alter_column("user_gear", "gear_model_id", new_column_name="gear_id")

    # Create old FK constraint pointing to gear
    op.create_foreign_key(
        "user_gear_gear_id_fkey",
        "user_gear",
        "gear",
        ["gear_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create old unique constraint
    op.create_unique_constraint(
        "uq_user_gear_user_gear",
        "user_gear",
        ["user_id", "gear_id"],
    )

    # Create old index
    op.create_index("ix_user_gear_gear_id", "user_gear", ["gear_id"])
