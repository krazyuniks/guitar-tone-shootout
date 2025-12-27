"""SQLite registry for worktree management.

Provides ACID-compliant storage for worktree metadata, port allocations,
and git state tracking.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import (
    PortConfig,
    VolumeConfig,
    calculate_ports,
    calculate_volumes,
    get_compose_project_name,
    get_registry_path,
    settings,
)


@dataclass
class Worktree:
    """Represents a registered worktree."""

    id: int
    branch: str
    worktree_name: str
    worktree_path: str
    compose_project: str
    status: str
    offset: int
    created_at: str
    ports: PortConfig
    volumes: VolumeConfig

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.ports.frontend}"

    @property
    def backend_url(self) -> str:
        return f"http://localhost:{self.ports.backend}"

    @property
    def cloudbeaver_url(self) -> str:
        return f"http://localhost:{self.ports.cloudbeaver}"


@dataclass
class GitState:
    """Represents the git state tracking."""

    local_main_commit: str | None
    remote_main_commit: str | None
    last_synced_at: str | None


class RegistryError(Exception):
    """Base exception for registry operations."""


class WorktreeNotFoundError(RegistryError):
    """Worktree not found in registry."""


class WorktreeExistsError(RegistryError):
    """Worktree already exists in registry."""


class NoAvailableOffsetError(RegistryError):
    """No available port offset found."""


SCHEMA_VERSION = "1.1"

SCHEMA_SQL = """
-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_info (
    version TEXT PRIMARY KEY,
    migrated_at TEXT NOT NULL
);

-- Worktree registry
CREATE TABLE IF NOT EXISTS worktrees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch TEXT NOT NULL UNIQUE,
    worktree_name TEXT NOT NULL UNIQUE,
    worktree_path TEXT NOT NULL,
    compose_project TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    offset INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    port_frontend INTEGER NOT NULL,
    port_backend INTEGER NOT NULL,
    port_db INTEGER NOT NULL,
    port_redis INTEGER NOT NULL,
    port_cloudbeaver INTEGER NOT NULL DEFAULT 8978,
    volume_postgres TEXT NOT NULL,
    volume_redis TEXT NOT NULL,
    volume_uploads TEXT NOT NULL,
    volume_cloudbeaver TEXT NOT NULL DEFAULT ''
);

-- Git state tracking (singleton)
CREATE TABLE IF NOT EXISTS git_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    local_main_commit TEXT,
    remote_main_commit TEXT,
    last_synced_at TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_worktrees_status ON worktrees(status);
CREATE INDEX IF NOT EXISTS idx_worktrees_offset ON worktrees(offset);
CREATE UNIQUE INDEX IF NOT EXISTS idx_worktrees_offset_active
    ON worktrees(offset) WHERE status = 'active';
"""


@contextmanager
def get_db(registry_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager for database connections.

    Provides automatic commit on success and rollback on failure.

    Args:
        registry_path: Optional path override for the registry database

    Yields:
        sqlite3.Connection with Row factory
    """
    path = registry_path or get_registry_path()
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_1_0_to_1_1(conn: sqlite3.Connection) -> None:
    """Migrate schema from 1.0 to 1.1 (add cloudbeaver columns)."""
    # Check if columns already exist
    cursor = conn.execute("PRAGMA table_info(worktrees)")
    columns = {row[1] for row in cursor.fetchall()}

    if "port_cloudbeaver" not in columns:
        # Add cloudbeaver port column with calculated default based on offset
        conn.execute(
            "ALTER TABLE worktrees ADD COLUMN port_cloudbeaver INTEGER NOT NULL DEFAULT 8978"
        )
        # Update existing rows with correct calculated port
        conn.execute(
            """
            UPDATE worktrees
            SET port_cloudbeaver = 8978 + (offset * 10)
            """
        )

    if "volume_cloudbeaver" not in columns:
        conn.execute(
            "ALTER TABLE worktrees ADD COLUMN volume_cloudbeaver TEXT NOT NULL DEFAULT ''"
        )
        # Update existing rows with correct volume name
        conn.execute(
            """
            UPDATE worktrees
            SET volume_cloudbeaver = 'gts-' || LOWER(REPLACE(worktree_name, '/', '-')) || '-cloudbeaver'
            """
        )


def init_registry(registry_path: Path | None = None) -> None:
    """Initialize the registry database with schema.

    Safe to call multiple times - uses CREATE IF NOT EXISTS.

    Args:
        registry_path: Optional path override
    """
    path = registry_path or get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with get_db(path) as conn:
        conn.executescript(SCHEMA_SQL)

        # Check current schema version and migrate if needed
        try:
            row = conn.execute(
                "SELECT version FROM schema_info ORDER BY version DESC LIMIT 1"
            ).fetchone()
            current_version = row["version"] if row else None
        except sqlite3.OperationalError:
            current_version = None

        # Apply migrations
        if current_version is None or current_version == "1.0":
            _migrate_1_0_to_1_1(conn)

        # Insert or update schema version
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_info (version, migrated_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now),
        )

        # Initialize git state singleton
        conn.execute(
            "INSERT OR IGNORE INTO git_state (id, last_synced_at) VALUES (1, ?)",
            (now,),
        )


def find_available_offset() -> int:
    """Find the smallest available port offset.

    Scans for gaps in used offsets to reuse freed slots.

    Returns:
        The smallest available offset (0 for main if not taken)

    Raises:
        NoAvailableOffsetError: If max_worktrees limit reached
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT offset FROM worktrees WHERE status = 'active' ORDER BY offset"
        ).fetchall()

        used_offsets = {row["offset"] for row in rows}

        # Find first gap or next available
        offset = 0
        while offset in used_offsets:
            offset += 1
            if offset >= settings.max_worktrees:
                raise NoAvailableOffsetError(
                    f"Maximum worktrees ({settings.max_worktrees}) reached. "
                    "Teardown unused worktrees first."
                )

        return offset


def register_worktree(
    branch: str,
    worktree_name: str,
    worktree_path: Path,
    offset: int | None = None,
) -> Worktree:
    """Register a new worktree in the database.

    Args:
        branch: Git branch name (e.g., "main", "42/feature-audio")
        worktree_name: Directory name (e.g., "main", "42-feature-audio")
        worktree_path: Absolute path to worktree
        offset: Port offset (auto-allocated if None)

    Returns:
        The created Worktree record

    Raises:
        WorktreeExistsError: If branch or name already registered
    """
    if offset is None:
        offset = find_available_offset()

    ports = calculate_ports(offset)
    volumes = calculate_volumes(worktree_name)
    compose_project = get_compose_project_name(worktree_name)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO worktrees (
                    branch, worktree_name, worktree_path, compose_project,
                    status, offset, created_at,
                    port_frontend, port_backend, port_db, port_redis, port_cloudbeaver,
                    volume_postgres, volume_redis, volume_uploads, volume_cloudbeaver
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch,
                    worktree_name,
                    str(worktree_path),
                    compose_project,
                    offset,
                    now,
                    ports.frontend,
                    ports.backend,
                    ports.db,
                    ports.redis,
                    ports.cloudbeaver,
                    volumes.postgres,
                    volumes.redis,
                    volumes.uploads,
                    volumes.cloudbeaver,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise WorktreeExistsError(
                f"Worktree already registered: {branch} or {worktree_name}"
            ) from e

        return Worktree(
            id=cursor.lastrowid,
            branch=branch,
            worktree_name=worktree_name,
            worktree_path=str(worktree_path),
            compose_project=compose_project,
            status="active",
            offset=offset,
            created_at=now,
            ports=ports,
            volumes=volumes,
        )


def get_worktree(name_or_branch: str) -> Worktree:
    """Get a worktree by name or branch.

    Args:
        name_or_branch: Worktree name or branch name

    Returns:
        Worktree record

    Raises:
        WorktreeNotFoundError: If not found
    """
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM worktrees
            WHERE (worktree_name = ? OR branch = ?) AND status = 'active'
            """,
            (name_or_branch, name_or_branch),
        ).fetchone()

        if not row:
            raise WorktreeNotFoundError(f"Worktree not found: {name_or_branch}")

        return _row_to_worktree(row)


def get_worktree_by_path(path: Path) -> Worktree:
    """Get a worktree by its path.

    Args:
        path: Worktree directory path

    Returns:
        Worktree record

    Raises:
        WorktreeNotFoundError: If not found
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM worktrees WHERE worktree_path = ? AND status = 'active'",
            (str(path),),
        ).fetchone()

        if not row:
            raise WorktreeNotFoundError(f"Worktree not found at path: {path}")

        return _row_to_worktree(row)


def list_worktrees(include_removed: bool = False) -> list[Worktree]:
    """List all registered worktrees.

    Args:
        include_removed: Include worktrees marked as removed

    Returns:
        List of Worktree records
    """
    with get_db() as conn:
        if include_removed:
            rows = conn.execute("SELECT * FROM worktrees ORDER BY offset").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM worktrees WHERE status = 'active' ORDER BY offset"
            ).fetchall()

        return [_row_to_worktree(row) for row in rows]


def mark_worktree_removed(name_or_branch: str) -> None:
    """Mark a worktree as removed (soft delete).

    Args:
        name_or_branch: Worktree name or branch

    Raises:
        WorktreeNotFoundError: If not found
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE worktrees SET status = 'removed'
            WHERE (worktree_name = ? OR branch = ?) AND status = 'active'
            """,
            (name_or_branch, name_or_branch),
        )

        if cursor.rowcount == 0:
            raise WorktreeNotFoundError(f"Worktree not found: {name_or_branch}")


def delete_worktree(name_or_branch: str) -> None:
    """Permanently delete a worktree from registry.

    Args:
        name_or_branch: Worktree name or branch

    Raises:
        WorktreeNotFoundError: If not found
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM worktrees WHERE worktree_name = ? OR branch = ?",
            (name_or_branch, name_or_branch),
        )

        if cursor.rowcount == 0:
            raise WorktreeNotFoundError(f"Worktree not found: {name_or_branch}")


def get_git_state() -> GitState:
    """Get the current git state tracking."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM git_state WHERE id = 1").fetchone()

        if not row:
            return GitState(None, None, None)

        return GitState(
            local_main_commit=row["local_main_commit"],
            remote_main_commit=row["remote_main_commit"],
            last_synced_at=row["last_synced_at"],
        )


def update_git_state(
    local_main_commit: str | None = None,
    remote_main_commit: str | None = None,
) -> None:
    """Update git state tracking.

    Args:
        local_main_commit: Local main branch HEAD
        remote_main_commit: Remote main branch HEAD
    """
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        if local_main_commit is not None:
            conn.execute(
                "UPDATE git_state SET local_main_commit = ?, last_synced_at = ? WHERE id = 1",
                (local_main_commit, now),
            )
        if remote_main_commit is not None:
            conn.execute(
                "UPDATE git_state SET remote_main_commit = ?, last_synced_at = ? WHERE id = 1",
                (remote_main_commit, now),
            )


def prune_stale_entries() -> list[str]:
    """Remove registry entries for worktrees that no longer exist on disk.

    Returns:
        List of pruned worktree names
    """
    pruned = []

    with get_db() as conn:
        rows = conn.execute(
            "SELECT worktree_name, worktree_path FROM worktrees WHERE status = 'active'"
        ).fetchall()

        for row in rows:
            path = Path(row["worktree_path"])
            if not path.exists():
                conn.execute(
                    "UPDATE worktrees SET status = 'removed' WHERE worktree_name = ?",
                    (row["worktree_name"],),
                )
                pruned.append(row["worktree_name"])

    return pruned


def get_active_worktree_count() -> int:
    """Get count of active worktrees."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM worktrees WHERE status = 'active'"
        ).fetchone()
        return row["count"]


def _row_to_worktree(row: sqlite3.Row) -> Worktree:
    """Convert a database row to a Worktree object."""
    return Worktree(
        id=row["id"],
        branch=row["branch"],
        worktree_name=row["worktree_name"],
        worktree_path=row["worktree_path"],
        compose_project=row["compose_project"],
        status=row["status"],
        offset=row["offset"],
        created_at=row["created_at"],
        ports=PortConfig(
            frontend=row["port_frontend"],
            backend=row["port_backend"],
            db=row["port_db"],
            redis=row["port_redis"],
            cloudbeaver=row["port_cloudbeaver"],
        ),
        volumes=VolumeConfig(
            postgres=row["volume_postgres"],
            redis=row["volume_redis"],
            uploads=row["volume_uploads"],
            cloudbeaver=row["volume_cloudbeaver"],
        ),
    )
