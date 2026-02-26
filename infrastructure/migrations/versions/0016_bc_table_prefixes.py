"""Add bounded-context table prefixes.

Rename all 24 core tables to core_* prefix and 3 T3K staging tables
to semantic names. PostgreSQL auto-updates FK constraint targets when
tables are renamed.

Revision ID: 0016
Revises: 0015
Create Date: 2026-02-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (old_name, new_name)
CORE_RENAMES = [
    ("users", "core_users"),
    ("oauth_providers", "core_oauth_providers"),
    ("user_identities", "core_user_identities"),
    ("user_gear", "core_user_gear"),
    ("jobs", "core_jobs"),
    ("audit_logs", "core_audit_logs"),
    ("shootouts", "core_shootouts"),
    ("di_tracks", "core_di_tracks"),
    ("shootout_chains", "core_shootout_chains"),
    ("audio_segments", "core_audio_segments"),
    ("shootout_comments", "core_shootout_comments"),
    ("gear", "core_gear"),
    ("gear_makes", "core_gear_makes"),
    ("tags", "core_tags"),
    ("gear_tags", "core_gear_tags"),
    ("gear_models", "core_gear_models"),
    ("gear_sources", "core_gear_sources"),
    ("signal_chains", "core_signal_chains"),
    ("signal_chain_blocks", "core_signal_chain_blocks"),
    ("signal_chain_groups", "core_signal_chain_groups"),
    ("block_types", "core_block_types"),
    ("user_tags", "core_user_tags"),
    ("presets", "core_presets"),
    ("user_notifications", "core_user_notifications"),
]

T3K_RENAMES = [
    ("t3k_creators", "t3k_users_staging"),
    ("t3k_packs", "t3k_tones_staging"),
    ("t3k_models", "t3k_models_staging"),
]


def _table_exists(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in set(inspector.get_table_names())


def upgrade() -> None:
    for old_name, new_name in CORE_RENAMES:
        op.rename_table(old_name, new_name)
    for old_name, new_name in T3K_RENAMES:
        if _table_exists(new_name):
            # Target already exists — verify it's empty before replacing
            conn = op.get_bind()
            count = conn.execute(
                sa.select(sa.func.count()).select_from(sa.table(new_name))
            ).scalar()
            if count:
                raise RuntimeError(
                    f"Cannot rename {old_name} → {new_name}: "
                    f"target table already exists with {count} rows"
                )
            op.drop_table(new_name)
        op.rename_table(old_name, new_name)


def downgrade() -> None:
    for old_name, new_name in reversed(T3K_RENAMES):
        op.rename_table(new_name, old_name)
    for old_name, new_name in reversed(CORE_RENAMES):
        op.rename_table(new_name, old_name)
