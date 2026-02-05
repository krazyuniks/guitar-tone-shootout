"""add user is_active field

Revision ID: d557e77101af
Revises: b4a1fd310cb9
Create Date: 2026-02-05 14:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd557e77101af'
down_revision: str | Sequence[str] | None = 'b4a1fd310cb9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_active column to users table."""
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Remove is_active column from users table."""
    op.drop_column('users', 'is_active')
