"""SQLite registry for worktree management.

Provides ACID-compliant storage for worktree metadata, port allocations,
and git state tracking. Also includes orphan detection to find git worktrees
that are not tracked in the registry.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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
    def nginx_url(self) -> str:
        """User-facing entry point URL (nginx)."""
        return f"http://localhost:{self.ports.nginx}"

    @property
    def frontend_url(self) -> str:
        """User-facing URL - routes through nginx for consistent auth handling."""
        return f"http://localhost:{self.ports.nginx}"

    @property
    def astro_url(self) -> str:
        """Internal Astro dev server URL (for direct access/debugging)."""
        return f"http://localhost:{self.ports.astro}"

    @property
    def webapp_url(self) -> str:
        return f"http://localhost:{self.ports.webapp}"

    @property
    def cloudbeaver_url(self) -> str:
        return f"http://localhost:{self.ports.cloudbeaver}"

    @property
    def subdomain(self) -> str:
        """Subdomain for Traefik routing (e.g., 'dev' for main, '603' for issue worktrees)."""
        if self.worktree_name == "main":
            return "dev"
        # Extract issue number from branch like "603/improve-pack-count-display"
        if "/" in self.branch:
            try:
                return self.branch.split("/")[0]
            except (ValueError, IndexError):
                pass
        # Fallback to worktree name
        return self.worktree_name

    @property
    def router_name(self) -> str:
        """Unique Traefik router name."""
        if self.worktree_name == "main":
            return "gts-main"
        return f"gts-{self.subdomain}"


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


SCHEMA_VERSION = "1.3"

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
    port_nginx INTEGER NOT NULL DEFAULT 9000,
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
        conn.execute("ALTER TABLE worktrees ADD COLUMN volume_cloudbeaver TEXT NOT NULL DEFAULT ''")
        # Update existing rows with correct volume name
        conn.execute(
            """
            UPDATE worktrees
            SET volume_cloudbeaver = 'gts-' || LOWER(REPLACE(worktree_name, '/', '-')) || '-cloudbeaver'
            """
        )


def _migrate_1_1_to_1_2(conn: sqlite3.Connection) -> None:
    """Migrate schema from 1.1 to 1.2 (add nginx port column)."""
    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(worktrees)")
    columns = {row[1] for row in cursor.fetchall()}

    if "port_nginx" not in columns:
        # Add nginx port column with calculated default based on offset
        conn.execute("ALTER TABLE worktrees ADD COLUMN port_nginx INTEGER NOT NULL DEFAULT 9000")
        # Update existing rows with correct calculated port (9000 + offset * 10)
        conn.execute(
            """
            UPDATE worktrees
            SET port_nginx = 9000 + (offset * 10)
            """
        )


def _migrate_1_2_to_1_3(conn: sqlite3.Connection) -> None:
    """Migrate schema from 1.2 to 1.3 (fix volume naming pattern).

    Changes volume naming from gts-{worktree}-{type} to gts-{type}-{worktree}
    to match docker-compose.yml base pattern.
    """
    # Update volume names to correct pattern: gts-{type}-{worktree}
    conn.execute(
        """
        UPDATE worktrees
        SET
            volume_postgres = 'gts-postgres-' || LOWER(REPLACE(worktree_name, '/', '-')),
            volume_redis = 'gts-redis-' || LOWER(REPLACE(worktree_name, '/', '-')),
            volume_uploads = 'gts-uploads-' || LOWER(REPLACE(worktree_name, '/', '-')),
            volume_cloudbeaver = 'gts-cloudbeaver-' || LOWER(REPLACE(worktree_name, '/', '-'))
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

        # Apply migrations sequentially
        if current_version is None or current_version == "1.0":
            _migrate_1_0_to_1_1(conn)
            current_version = "1.1"

        if current_version == "1.1":
            _migrate_1_1_to_1_2(conn)
            current_version = "1.2"

        if current_version == "1.2":
            _migrate_1_2_to_1_3(conn)

        # Insert or update schema version
        now = datetime.now(UTC).isoformat()
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
    now = datetime.now(UTC).isoformat()

    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO worktrees (
                    branch, worktree_name, worktree_path, compose_project,
                    status, offset, created_at,
                    port_frontend, port_backend, port_db, port_redis, port_cloudbeaver, port_nginx,
                    volume_postgres, volume_redis, volume_uploads, volume_cloudbeaver
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch,
                    worktree_name,
                    str(worktree_path),
                    compose_project,
                    offset,
                    now,
                    ports.astro,  # DB column is port_frontend for compatibility
                    ports.webapp,  # DB column is port_backend for compatibility
                    ports.db,
                    ports.redis,
                    ports.cloudbeaver,
                    ports.nginx,
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

        # lastrowid is always set after successful INSERT
        assert cursor.lastrowid is not None
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
    """Get a worktree by name, branch, or issue number.

    Lookup order:
    1. Exact match on worktree_name
    2. Exact match on branch
    3. Issue number prefix match (e.g., "545" matches "545-p0-security-headers...")

    Args:
        name_or_branch: Worktree name, branch name, or issue number

    Returns:
        Worktree record

    Raises:
        WorktreeNotFoundError: If not found
    """
    with get_db() as conn:
        # First try exact match on name or branch
        row = conn.execute(
            """
            SELECT * FROM worktrees
            WHERE (worktree_name = ? OR branch = ?) AND status = 'active'
            """,
            (name_or_branch, name_or_branch),
        ).fetchone()

        if row:
            return _row_to_worktree(row)

        # If input looks like an issue number, try prefix match
        if name_or_branch.isdigit():
            issue_num = name_or_branch
            row = conn.execute(
                """
                SELECT * FROM worktrees
                WHERE (worktree_name LIKE ? OR branch LIKE ?)
                  AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (f"{issue_num}-%", f"{issue_num}/%"),
            ).fetchone()

            if row:
                return _row_to_worktree(row)

        raise WorktreeNotFoundError(f"Worktree not found: {name_or_branch}")


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
    now = datetime.now(UTC).isoformat()

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

    This function:
    1. Finds active entries whose paths no longer exist
    2. Deletes them from the database (not just marks as 'removed')
    3. Also cleans up any previously marked 'removed' entries

    Returns:
        List of pruned worktree names
    """
    pruned = []

    with get_db() as conn:
        # Find active entries with non-existent paths
        rows = conn.execute(
            "SELECT worktree_name, worktree_path FROM worktrees WHERE status = 'active'"
        ).fetchall()

        for row in rows:
            path = Path(row["worktree_path"])
            if not path.exists():
                # DELETE instead of marking as 'removed' to prevent stale entries
                conn.execute(
                    "DELETE FROM worktrees WHERE worktree_name = ?",
                    (row["worktree_name"],),
                )
                pruned.append(row["worktree_name"])

        # Also clean up any previously marked 'removed' entries
        removed_rows = conn.execute(
            "SELECT worktree_name FROM worktrees WHERE status = 'removed'"
        ).fetchall()

        for row in removed_rows:
            conn.execute(
                "DELETE FROM worktrees WHERE worktree_name = ?",
                (row["worktree_name"],),
            )
            if row["worktree_name"] not in pruned:
                pruned.append(row["worktree_name"])

    return pruned


def get_active_worktree_count() -> int:
    """Get count of active worktrees."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM worktrees WHERE status = 'active'"
        ).fetchone()
        return int(row["count"])


def _row_to_worktree(row: sqlite3.Row) -> Worktree:
    """Convert a database row to a Worktree object."""
    offset = row["offset"]
    http_offset = offset * settings.offset_multiplier_http
    worktree_name = row["worktree_name"]
    prefix = settings.compose_project_prefix
    safe_name = worktree_name.replace("/", "-").lower()

    return Worktree(
        id=row["id"],
        branch=row["branch"],
        worktree_name=worktree_name,
        worktree_path=row["worktree_path"],
        compose_project=row["compose_project"],
        status=row["status"],
        offset=offset,
        created_at=row["created_at"],
        ports=PortConfig(
            nginx=row["port_nginx"],  # User-facing entry point
            astro=row["port_frontend"],  # DB column kept as port_frontend for compatibility
            webapp=row["port_backend"],  # DB column kept as port_backend for compatibility
            db=row["port_db"],
            redis=row["port_redis"],
            cloudbeaver=row["port_cloudbeaver"],
            # Observability ports are calculated from offset (not stored in DB)
            grafana=settings.base_port_grafana + http_offset,
            prometheus=settings.base_port_prometheus + http_offset,
            loki=settings.base_port_loki + http_offset,
            tempo=settings.base_port_tempo + http_offset,
            otlp_grpc=settings.base_port_otlp_grpc + http_offset,
            otlp_http=settings.base_port_otlp_http + http_offset,
            alloy=settings.base_port_alloy + http_offset,
        ),
        volumes=VolumeConfig(
            postgres=row["volume_postgres"],
            redis=row["volume_redis"],
            uploads=row["volume_uploads"],
            cloudbeaver=row["volume_cloudbeaver"],
            # Observability volumes are calculated from worktree name (not stored in DB)
            grafana=f"{prefix}-{safe_name}-grafana",
            loki=f"{prefix}-{safe_name}-loki",
            tempo=f"{prefix}-{safe_name}-tempo",
            prometheus=f"{prefix}-{safe_name}-prometheus",
        ),
    )


# =============================================================================
# Orphan Detection
# =============================================================================


@dataclass
class OrphanedWorktree:
    """A git worktree that exists but is not in the registry."""

    path: Path
    branch: str
    commit: str
    reason: str  # Why it's considered orphaned


def find_orphaned_worktrees() -> list[OrphanedWorktree]:
    """Find git worktrees that exist but are not tracked in the registry.

    These are worktrees that appear in `git worktree list` but have no
    corresponding active entry in the registry database. They can occur when:
    - Registry was reset or corrupted
    - Worktree was created manually outside of worktree.py
    - Setup failed partway through and rollback was incomplete

    Returns:
        List of OrphanedWorktree objects for untracked worktrees.
    """
    from .git_ops import list_git_worktrees

    # Get all git worktrees
    git_worktrees = list_git_worktrees()

    # Get all registered worktrees (paths as strings)
    registered = list_worktrees(include_removed=False)
    registered_paths = {Path(wt.worktree_path).resolve() for wt in registered}

    orphans = []
    for git_wt in git_worktrees:
        resolved_path = git_wt.path.resolve()

        if resolved_path not in registered_paths:
            orphans.append(
                OrphanedWorktree(
                    path=git_wt.path,
                    branch=git_wt.branch,
                    commit=git_wt.commit,
                    reason="Not in registry (git worktree exists but not tracked)",
                )
            )

    return orphans


def add_orphan_to_registry(
    orphan: OrphanedWorktree,
    offset: int | None = None,
) -> Worktree:
    """Add an orphaned worktree to the registry.

    This reconciles the worktree by adding it to the database.
    Useful for recovering from registry corruption or manual worktree creation.

    Args:
        orphan: The orphaned worktree to register
        offset: Port offset to assign (auto-allocated if None)

    Returns:
        The newly registered Worktree

    Raises:
        WorktreeExistsError: If a worktree with this path/branch already exists
    """
    # Generate worktree name from directory
    worktree_name = orphan.path.name

    return register_worktree(
        branch=orphan.branch,
        worktree_name=worktree_name,
        worktree_path=orphan.path,
        offset=offset,
    )
