"""add audio metrics and reproducibility columns

Revision ID: a8f5d2c1b3e4
Revises: 13162ba0b3f0
Create Date: 2025-12-27 12:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f5d2c1b3e4"
down_revision: str | None = "13162ba0b3f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema.

    Adds:
    - processing_metadata JSONB to shootouts (for reproducibility)
    - start_ms and end_ms to tone_selections (segment timestamps)
    - audio_metrics JSONB to tone_selections (extracted metrics)
    - ai_evaluation JSONB to tone_selections (AI-generated analysis)
    """
    # Add processing_metadata to shootouts for reproducibility
    op.add_column(
        "shootouts",
        sa.Column(
            "processing_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Add segment timestamps to tone_selections
    op.add_column(
        "tone_selections",
        sa.Column("start_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tone_selections",
        sa.Column("end_ms", sa.Integer(), nullable=True),
    )

    # Add audio_metrics to tone_selections (stores extracted audio metrics)
    op.add_column(
        "tone_selections",
        sa.Column(
            "audio_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Add ai_evaluation to tone_selections (stores AI-generated evaluation)
    op.add_column(
        "tone_selections",
        sa.Column(
            "ai_evaluation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Remove ai_evaluation from tone_selections
    op.drop_column("tone_selections", "ai_evaluation")

    # Remove audio_metrics from tone_selections
    op.drop_column("tone_selections", "audio_metrics")

    # Remove segment timestamps from tone_selections
    op.drop_column("tone_selections", "end_ms")
    op.drop_column("tone_selections", "start_ms")

    # Remove processing_metadata from shootouts
    op.drop_column("shootouts", "processing_metadata")
