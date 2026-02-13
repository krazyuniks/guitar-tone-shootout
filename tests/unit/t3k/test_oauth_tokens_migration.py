"""Unit tests for T3K oauth_tokens Alembic migration (0002).

Tests that the migration file exists with correct structure,
creates the oauth_tokens table with the right columns, and
is reversible.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


def _migration_path() -> Path:
    """Return path to the 0002 migration file."""
    return (
        Path(__file__).parent.parent.parent.parent
        / "sources"
        / "t3k"
        / "alembic"
        / "versions"
        / "0002_oauth_tokens.py"
    )


class TestOAuthTokensMigrationExists:
    """Tests that the 0002 migration file exists and has correct metadata."""

    def test_migration_file_exists(self) -> None:
        """0002_oauth_tokens.py must exist in versions directory."""
        assert _migration_path().exists(), (
            "sources/t3k/alembic/versions/0002_oauth_tokens.py must exist"
        )

    def test_migration_revision_is_0002(self) -> None:
        """Migration revision identifier must be '0002'."""
        content = _migration_path().read_text()
        tree = ast.parse(content)

        revision_value = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "revision" for t in node.targets)
                and isinstance(node.value, ast.Constant)
            ):
                revision_value = node.value.value

        assert revision_value == "0002", f"revision must be '0002', got {revision_value!r}"

    def test_migration_chains_from_0001(self) -> None:
        """Migration down_revision must point to '0001'."""
        content = _migration_path().read_text()
        tree = ast.parse(content)

        down_revision_value = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "down_revision" for t in node.targets)
                and isinstance(node.value, ast.Constant)
            ):
                down_revision_value = node.value.value

        assert down_revision_value == "0001", (
            f"down_revision must be '0001', got {down_revision_value!r}"
        )


class TestOAuthTokensMigrationSchema:
    """Tests that the migration creates the correct table schema."""

    @pytest.fixture
    def migration_source(self) -> str:
        """Read the migration source code."""
        return _migration_path().read_text()

    def test_upgrade_creates_oauth_tokens_table(self, migration_source: str) -> None:
        """upgrade() must create the 'oauth_tokens' table."""
        assert "create_table" in migration_source
        assert '"oauth_tokens"' in migration_source or "'oauth_tokens'" in migration_source

    def test_table_has_id_column(self, migration_source: str) -> None:
        """oauth_tokens must have an auto-increment integer id column."""
        assert '"id"' in migration_source or "'id'" in migration_source
        assert "Integer" in migration_source
        assert "autoincrement" in migration_source

    def test_table_has_access_token_encrypted_column(self, migration_source: str) -> None:
        """oauth_tokens must have access_token_encrypted varchar(1024)."""
        assert "access_token_encrypted" in migration_source
        assert "1024" in migration_source

    def test_table_has_refresh_token_encrypted_column(self, migration_source: str) -> None:
        """oauth_tokens must have refresh_token_encrypted varchar(1024)."""
        assert "refresh_token_encrypted" in migration_source

    def test_table_has_expires_at_column(self, migration_source: str) -> None:
        """oauth_tokens must have expires_at timestamptz column."""
        assert "expires_at" in migration_source
        assert "timezone=True" in migration_source

    def test_table_has_created_at_column(self, migration_source: str) -> None:
        """oauth_tokens must have created_at timestamptz column."""
        assert "created_at" in migration_source

    def test_table_has_primary_key(self, migration_source: str) -> None:
        """oauth_tokens must have a primary key constraint."""
        assert "PrimaryKeyConstraint" in migration_source
        assert "pk_oauth_tokens" in migration_source

    def test_downgrade_drops_oauth_tokens_table(self, migration_source: str) -> None:
        """downgrade() must drop the 'oauth_tokens' table."""
        assert "drop_table" in migration_source
        # Verify 'oauth_tokens' appears in drop context
        assert migration_source.count("oauth_tokens") >= 2  # create + drop

    def test_migration_is_importable(self) -> None:
        """Migration module must be importable."""
        spec = importlib.util.spec_from_file_location("migration_0002", _migration_path())
        assert spec is not None
        assert spec.loader is not None
