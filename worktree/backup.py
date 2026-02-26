"""Database backup and restore for GTS worktrees.

Discovers databases dynamically from the running PostgreSQL instance.
No hardcoded database names — the pg_database catalog is the source of truth.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from .config import get_backups_dir


class BackupError(Exception):
    """Raised when a backup or restore operation fails."""


def _check_db_running(worktree_path: Path) -> None:
    """Verify the db container is running."""
    result = subprocess.run(
        ["docker", "compose", "ps", "--status", "running", "--format", "{{.Service}}", "db"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if "db" not in result.stdout:
        raise BackupError("Database container is not running")


def discover_databases(worktree_path: Path) -> list[str]:
    """Discover all application databases from the running PostgreSQL instance.

    Queries pg_database catalog, excludes templates and the default 'postgres' DB.

    Returns:
        Sorted list of database names (e.g. ['gts_core']).
    """
    _check_db_running(worktree_path)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "gts",
            "-d",
            "postgres",
            "-t",
            "-A",
            "-c",
            "SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres' ORDER BY datname",
        ],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise BackupError(f"Failed to discover databases: {result.stderr.strip()}")

    databases = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    if not databases:
        raise BackupError("No application databases found")
    return databases


def ensure_backups_dir() -> Path:
    """Ensure the backups directory exists with proper .gitignore.

    Creates:
        - guitar-tone-worktrees/backups/
        - guitar-tone-worktrees/backups/.gitignore
    """
    backups_dir = get_backups_dir()
    backups_dir.mkdir(parents=True, exist_ok=True)

    gitignore_path = backups_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            "# Database backup files\n"
            "*.dump\n"
            "*.sql.gz\n"
            "*.sql\n"
            "\n"
            "# Keep this directory (and .gitignore)\n"
            "!.gitignore\n"
        )

    return backups_dir


def backup_database(worktree_path: Path, db_name: str) -> Path:
    """Back up a single database to a timestamped dump file.

    Runs pg_dump inside the db container, writes to ../backups/{db_name}.{timestamp}.dump.

    Returns:
        Path to the created backup file.
    """
    _check_db_running(worktree_path)
    backups_dir = ensure_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_file = backups_dir / f"{db_name}.{timestamp}.dump"

    with open(backup_file, "wb") as f:
        proc = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "pg_dump", "-Fc", "-U", "gts", db_name],
            cwd=worktree_path,
            stdout=f,
            stderr=subprocess.PIPE,
            timeout=300,
        )

    if proc.returncode != 0:
        backup_file.unlink(missing_ok=True)
        raise BackupError(f"pg_dump failed for {db_name}: {proc.stderr.decode().strip()}")

    size = backup_file.stat().st_size
    if size < 100:
        backup_file.unlink(missing_ok=True)
        raise BackupError(f"Backup file too small for {db_name} (database may be empty)")

    return backup_file


def backup_all_databases(worktree_path: Path) -> list[Path]:
    """Back up all discovered databases.

    Returns:
        List of paths to created backup files.
    """
    databases = discover_databases(worktree_path)
    backup_files = []
    for db_name in databases:
        backup_file = backup_database(worktree_path, db_name)
        backup_files.append(backup_file)
    return backup_files


def restore_database(worktree_path: Path, backup_file: Path, db_name: str) -> None:
    """Restore a database from a pg_dump custom format file.

    Terminates connections, drops, recreates, and restores.
    """
    _check_db_running(worktree_path)

    # Terminate existing connections
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "gts",
            "-d",
            "postgres",
            "-c",
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db_name}' AND pid <> pg_backend_pid();",
        ],
        cwd=worktree_path,
        capture_output=True,
        timeout=30,
    )

    # Drop database
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "dropdb", "-U", "gts", "--if-exists", db_name],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise BackupError(f"Failed to drop {db_name}: {result.stderr.strip()}")

    # Create database
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "createdb", "-U", "gts", db_name],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise BackupError(f"Failed to create {db_name}: {result.stderr.strip()}")

    # Restore from dump
    with open(backup_file, "rb") as f:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "gts",
                "-d",
                db_name,
                "--no-owner",
                "--no-privileges",
            ],
            cwd=worktree_path,
            stdin=f,
            capture_output=True,
            timeout=600,
        )

    # pg_restore returns non-zero on warnings (e.g. "role does not exist"), which is OK
    if proc.returncode != 0 and b"FATAL" in proc.stderr:
        raise BackupError(f"pg_restore failed for {db_name}: {proc.stderr.decode().strip()}")


def get_latest_backup(db_name: str) -> Path | None:
    """Get the most recent backup file for a specific database.

    Scans ../backups/ for {db_name}.*.dump files, returns the newest.
    """
    backups_dir = get_backups_dir()
    if not backups_dir.exists():
        return None

    backups = list(backups_dir.glob(f"{db_name}.*.dump"))
    if not backups:
        return None

    return sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def get_latest_backups() -> dict[str, Path | None]:
    """Get the latest backup file for each database found in ../backups/.

    Discovers database names from existing backup filenames.

    Returns:
        Dict mapping database name to latest backup path (or None).
    """
    backups_dir = get_backups_dir()
    if not backups_dir.exists():
        return {}

    # Discover database names from backup filenames: {db_name}.{timestamp}.dump
    db_names: set[str] = set()
    for dump_file in backups_dir.glob("*.dump"):
        parts = dump_file.stem.rsplit(".", 1)
        if len(parts) == 2:
            db_names.add(parts[0])

    return {db_name: get_latest_backup(db_name) for db_name in sorted(db_names)}
