# Backup Automation & Mock Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Multi-database backup automation (host CLI + scheduler) and remove all unittest.mock usage from 25 test files.

**Architecture:** Two independent workstreams — backup infrastructure (worktree.py + scheduler) and mock audit (test rewrites). Backup is additive. Mock audit is file-by-file replacement.

**Tech Stack:** Python 3.14, pg_dump, TaskIQ scheduler, SQLAlchemy 2.0, httpx.MockTransport, pytest

---

## Phase 1: Backup Infrastructure (worktree.py)

### Task 1: Create `worktree/backup.py` with database discovery

**Files:**
- Create: `worktree/backup.py`
- Modify: `worktree/docker.py` (remove `export_database`, `ensure_backups_dir`)

**Step 1: Create `worktree/backup.py`**

```python
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
        Sorted list of database names (e.g. ['gts_core', 'gts_t3k_source']).
    """
    _check_db_running(worktree_path)
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "db",
            "psql", "-U", "gts", "-d", "postgres", "-t", "-A", "-c",
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
            "*.sql\n"
            "*.tar\n"
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
```

**Step 2: Remove old functions from `worktree/docker.py`**

Remove `ensure_backups_dir` and `export_database` from `worktree/docker.py`. Update all imports that referenced them to import from `worktree/backup.py` instead.

Search for references:
- `worktree/commands/services.py` imports `export_database` from `worktree/docker.py`
- `worktree/commands/setup.py` may reference `ensure_backups_dir` or backup patterns

**Step 3: Update imports in referencing files**

In `worktree/commands/services.py`:
```python
# Old:
from ..docker import DockerError, export_database, start_services, stop_services, wait_for_healthy
# New:
from ..backup import BackupError, backup_all_databases
from ..docker import DockerError, start_services, stop_services, wait_for_healthy
```

**Step 4: Verify no broken imports**

Run: `just lint`
Expected: PASS

**Step 5: Commit**

```bash
git add worktree/backup.py worktree/docker.py worktree/commands/services.py worktree/commands/setup.py
git commit -m "refactor: extract backup logic into worktree/backup.py with multi-db support"
```

---

### Task 2: CLI subcommands — `backup` and `restore`

**Files:**
- Modify: `worktree/commands/services.py`

**Step 1: Replace `db-export` with `backup` command and add `restore`**

Replace the existing `db_export` command with `backup` (backs up all databases). Add `restore` command.

```python
@app.command("backup")
def backup_cmd() -> None:
    """Back up all databases to timestamped files in ../backups/."""
    try:
        current_path = get_current_worktree_path()
        get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1) from None

    try:
        from ..backup import backup_all_databases

        with console.status("[bold green]Backing up databases..."):
            backup_files = backup_all_databases(current_path)
        for bf in backup_files:
            size = bf.stat().st_size
            size_mb = size / (1024 * 1024)
            print_success(f"{bf.name} ({size_mb:.1f} MB)")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from None

@app.command("restore")
def restore_cmd(
    file: Path = typer.Argument(..., help="Path to .dump file to restore"),
) -> None:
    """Restore a database from a dump file.

    The database name is inferred from the filename (e.g. gts_core.20260217_1200.dump → gts_core).
    WARNING: This drops and recreates the target database!
    """
    try:
        current_path = get_current_worktree_path()
        get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1) from None

    if not file.exists():
        print_error(f"File not found: {file}")
        raise typer.Exit(1) from None

    # Infer database name from filename: {db_name}.{timestamp}.dump
    parts = file.stem.rsplit(".", 1)
    if len(parts) != 2 or not file.name.endswith(".dump"):
        print_error(f"Expected filename format: {{db_name}}.{{timestamp}}.dump, got: {file.name}")
        raise typer.Exit(1) from None

    db_name = parts[0]
    console.print(f"Restoring [cyan]{db_name}[/cyan] from {file.name}...")

    from ..backup import restore_database
    try:
        with console.status(f"[bold green]Restoring {db_name}..."):
            restore_database(current_path, file, db_name)
        print_success(f"Database {db_name} restored from {file.name}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from None
```

**Step 2: Add `restore_database` function to `worktree/backup.py`**

```python
def restore_database(worktree_path: Path, backup_file: Path, db_name: str) -> None:
    """Restore a database from a pg_dump custom format file.

    Terminates connections, drops, recreates, and restores.
    """
    _check_db_running(worktree_path)

    # Terminate existing connections
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "db",
            "psql", "-U", "gts", "-d", "postgres", "-c",
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
                "docker", "compose", "exec", "-T", "db",
                "pg_restore", "-U", "gts", "-d", db_name, "--no-owner", "--no-privileges",
            ],
            cwd=worktree_path,
            stdin=f,
            capture_output=True,
            timeout=600,
        )

    # pg_restore returns non-zero on warnings (e.g. "role does not exist"), which is OK
    if proc.returncode != 0 and b"FATAL" in proc.stderr:
        raise BackupError(f"pg_restore failed for {db_name}: {proc.stderr.decode().strip()}")
```

**Step 3: Update justfile**

Replace `db-export` with `db-backup`. Keep `db-import` for backwards compat but update it.

```just
# Back up all databases to ../backups/
db-backup:
    ./worktree.py backup

# Restore a database from a dump file
# Usage: just db-restore path/to/gts_core.20260217_1200.dump
db-restore file:
    ./worktree.py restore {{file}}
```

**Step 4: Run lint**

Run: `just lint`
Expected: PASS

**Step 5: Commit**

```bash
git add worktree/commands/services.py worktree/backup.py justfile
git commit -m "feat: add backup/restore CLI commands with multi-database support"
```

---

### Task 3: Update setup to use multi-database backup/restore

**Files:**
- Modify: `worktree/commands/setup.py`

**Step 1: Update `_get_or_create_backup` to handle multiple databases**

Replace `_get_latest_backup` (which looks for `shootout.*.dump`) with calls to `backup.get_latest_backups()`. Update `_get_or_create_backup` to return `dict[str, Path]` instead of `Path | None`.

**Step 2: Update `_import_database` to restore each database**

Loop over backup files, calling `backup.restore_database()` for each.

**Step 3: Handle backwards compatibility**

Old backups named `shootout.*.dump` should still be found — add a migration path that checks for old naming pattern and treats them as `gts_core` backups.

**Step 4: Test manually**

Run: `./worktree.py backup` then verify files in `../backups/`
Expected: Two files: `gts_core.{timestamp}.dump` and `gts_t3k_source.{timestamp}.dump`

**Step 5: Commit**

```bash
git add worktree/commands/setup.py
git commit -m "refactor: setup uses multi-database backup/restore"
```

---

### Task 4: Health & status integration

**Files:**
- Modify: `worktree/health.py`
- Modify: `worktree/commands/info.py`
- Modify: `.claude/commands/status.md`

**Step 1: Add backup fields to `HealthCheckResult`**

```python
from datetime import datetime
from .backup import get_latest_backups
from .config import get_backups_dir

@dataclass
class HealthCheckResult:
    healthy: bool
    services: dict[str, str]
    nginx_responding: bool
    webapp_responding: bool
    issues: list[str]
    worktree_path: Path | None = None
    last_backup: dict[str, datetime | None] = field(default_factory=dict)
    backup_stale: bool = False
```

**Step 2: Populate backup fields in `check_worktree_health`**

After existing checks, scan backup directory:

```python
# Check backup status
backups = get_latest_backups()
now = datetime.now()
stale_threshold = now - timedelta(hours=24)
backup_stale = False

last_backup = {}
for db_name, backup_path in backups.items():
    if backup_path:
        mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
        last_backup[db_name] = mtime
        if mtime < stale_threshold:
            backup_stale = True
    else:
        last_backup[db_name] = None
        backup_stale = True
```

**Step 3: Add backup display to `info.py` health and status commands**

In the `health` command output, after services:
```
Backups:
  gts_core:        2h ago (gts_core.20260217_1000.dump, 45MB)
  gts_t3k_source:  ⚠ 3d ago (stale)
```

In the `status` command panel, add a Backups section.

**Step 4: Update `/status` skill**

Add backup check to `.claude/commands/status.md` commands section and output format.

**Step 5: Commit**

```bash
git add worktree/health.py worktree/commands/info.py .claude/commands/status.md
git commit -m "feat: add backup status to health check and /status output"
```

---

### Task 5: Scheduler backup task

**Files:**
- Modify: `infrastructure/docker/Dockerfile.dev` (add `postgresql-client`)
- Modify: `docker-compose.yml` (add backups bind mount + DB_PASSWORD env to scheduler)
- Create: `apps/scheduler/src/scheduler/schedules/backup.py`
- Modify: `apps/scheduler/src/scheduler/main.py` (import new schedule)

**Step 1: Add `postgresql-client` to Dockerfile.dev**

In the first `apt-get install` block, add `postgresql-client` after `git`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libsndfile1 \
    ffmpeg \
    git \
    postgresql-client \
```

**Step 2: Add backups volume and DB_PASSWORD to scheduler in docker-compose.yml**

```yaml
scheduler:
    # ... existing config ...
    environment:
      DATABASE_URL: postgresql+asyncpg://gts:${DB_PASSWORD:-gts_dev_password}@db:5432/gts_core
      DB_PASSWORD: ${DB_PASSWORD:-gts_dev_password}
      REDIS_URL: redis://redis:6379
      # ...
    volumes:
      - ./libs:/app/libs:ro
      - ./apps/scheduler:/app/apps/scheduler
      - ./sources:/app/sources:ro
      - ../backups:/app/backups    # NEW: shared backup directory
```

**Step 3: Create `apps/scheduler/src/scheduler/schedules/backup.py`**

```python
"""Scheduled database backups.

Runs every 12 hours. Discovers all databases from PostgreSQL catalog,
dumps each to /app/backups/{db_name}.{timestamp}.dump using pg_dump.
Cleans up backups older than BACKUP_RETENTION_DAYS (default: 7).
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BACKUPS_DIR = Path("/app/backups")


def _parse_db_connection() -> tuple[str, str, str]:
    """Parse host, user, password from DATABASE_URL.

    Returns:
        (host, user, password) tuple.
    """
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        msg = "DATABASE_URL not set"
        raise ValueError(msg)

    # DATABASE_URL format: postgresql+asyncpg://user:password@host:port/dbname
    parsed = urlparse(database_url.replace("+asyncpg", ""))
    return parsed.hostname or "db", parsed.username or "gts", parsed.password or ""


def _discover_databases(host: str, user: str, password: str) -> list[str]:
    """Discover application databases from PostgreSQL catalog."""
    env = {**os.environ, "PGPASSWORD": password}
    result = subprocess.run(
        [
            "psql", "-h", host, "-U", user, "-d", "postgres", "-t", "-A", "-c",
            "SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres' ORDER BY datname",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Database discovery failed: {result.stderr.strip()}")

    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def _cleanup_old_backups(retention_days: int) -> None:
    """Delete backup files older than retention_days."""
    if not _BACKUPS_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    for dump_file in _BACKUPS_DIR.glob("*.dump"):
        mtime = datetime.fromtimestamp(dump_file.stat().st_mtime)
        if mtime < cutoff:
            dump_file.unlink()
            logger.info("Deleted old backup: %s", dump_file.name)


async def backup_all_databases() -> None:
    """Discover and back up all application databases.

    Writes pg_dump custom format files to /app/backups/.
    Cleans up old backups after successful run.
    """
    host, user, password = _parse_db_connection()
    databases = _discover_databases(host, user, password)

    if not databases:
        logger.warning("No databases found to back up")
        return

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    env = {**os.environ, "PGPASSWORD": password}

    for db_name in databases:
        backup_file = _BACKUPS_DIR / f"{db_name}.{timestamp}.dump"
        try:
            with open(backup_file, "wb") as f:
                proc = subprocess.run(
                    ["pg_dump", "-h", host, "-U", user, "-Fc", db_name],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    timeout=300,
                    env=env,
                )

            if proc.returncode != 0:
                backup_file.unlink(missing_ok=True)
                logger.error("pg_dump failed for %s: %s", db_name, proc.stderr.decode().strip())
                continue

            size = backup_file.stat().st_size
            if size < 100:
                backup_file.unlink(missing_ok=True)
                logger.error("Backup too small for %s — database may be empty", db_name)
                continue

            size_mb = size / (1024 * 1024)
            logger.info("Backed up %s: %s (%.1f MB)", db_name, backup_file.name, size_mb)

        except Exception:
            backup_file.unlink(missing_ok=True)
            logger.exception("Failed to back up %s", db_name)

    # Clean up old backups
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    _cleanup_old_backups(retention_days)


class _Schedule:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds


backup_all_databases.labels = {"schedule": [_Schedule(43200)]}  # type: ignore[attr-defined]  # 12 hours
```

**Step 4: Register in scheduler main**

Add to `apps/scheduler/src/scheduler/main.py`:

```python
from scheduler.schedules import backup as _backup_schedules  # noqa: F401
```

**Step 5: Rebuild and verify**

Run: `just build` (rebuilds Docker images with postgresql-client)
Run: `just up-d` (restarts with new volume mount)
Run: `docker compose exec scheduler pg_dump --version` (verify pg_dump available)

**Step 6: Commit**

```bash
git add infrastructure/docker/Dockerfile.dev docker-compose.yml apps/scheduler/src/scheduler/schedules/backup.py apps/scheduler/src/scheduler/main.py
git commit -m "feat: add twice-daily scheduled database backups to scheduler"
```

---

## Phase 2: Mock Audit — Worker Tests (Priority 1)

### Task 6: Rewrite `test_audio_job.py` (16 tests)

**Files:**
- Modify: `tests/unit/worker/test_audio_job.py`

**Context:** This file mocks `session.execute`, `execute_signal_chain`, `measure_loudness`, `sf` (soundfile), and `Path`. The 28 failures come from mocked session returning wrong types.

**Step 1: Read the current test file and the production code it tests**

Read: `tests/unit/worker/test_audio_job.py`
Read: `apps/worker/src/worker/jobs/audio.py`

Understand what each test asserts. Map each test to the production behaviour it validates.

**Step 2: Rewrite with real DB fixtures**

- Keep the existing `db_engine` and `db_session` fixtures (they use in-memory SQLite)
- Remove ALL `from unittest.mock import ...` lines
- Remove ALL `@patch(...)` decorators
- Create real `Job`, `ShootoutChain`, `GearModel` objects in the test database
- For `execute_signal_chain` and `measure_loudness`: these are audio processing functions that need real audio files. Use `tmp_path` with small test WAV files, or if the functions are too heavy, create lightweight test doubles (plain functions, not Mock objects)
- For `soundfile` (sf): use real soundfile library with temp files, or create a test helper function
- For `Path`: use real `pathlib.Path` with `tmp_path`

**Step 3: Run tests**

Run: `just tdd tests/unit/worker/test_audio_job.py`
Expected: All 16 tests PASS

**Step 4: Commit**

```bash
git add tests/unit/worker/test_audio_job.py
git commit -m "test: rewrite test_audio_job with real DB fixtures, remove unittest.mock"
```

---

### Task 7: Rewrite `test_master_audio.py` (13 tests)

**Files:**
- Modify: `tests/unit/worker/test_master_audio.py`

Same pattern as Task 6. Read production code, replace mocks with real fixtures.

**Step 1: Read and understand**

Read: `tests/unit/worker/test_master_audio.py`
Read: `apps/worker/src/worker/jobs/master_audio.py`

**Step 2: Rewrite with real DB + temp files**

Same approach: real SQLite sessions, real Path objects with `tmp_path`, real soundfile or test helpers.

**Step 3: Run tests**

Run: `just tdd tests/unit/worker/test_master_audio.py`
Expected: All 13 tests PASS

**Step 4: Commit**

```bash
git add tests/unit/worker/test_master_audio.py
git commit -m "test: rewrite test_master_audio with real DB fixtures, remove unittest.mock"
```

---

### Task 8: Rewrite `test_shootout_orchestrator.py` (18 tests)

**Files:**
- Modify: `tests/unit/worker/test_shootout_orchestrator.py`

**Step 1: Read and understand**

Read: `tests/unit/worker/test_shootout_orchestrator.py`
Read: `apps/worker/src/worker/jobs/shootout.py`

**Step 2: Rewrite with real DB**

This is the most straightforward of the three — mainly mocked sessions. Replace with real `db_session`, create real `Shootout`, `ShootoutChain`, `Job` objects.

**Step 3: Run tests**

Run: `just tdd tests/unit/worker/test_shootout_orchestrator.py`
Expected: All 18 tests PASS

**Step 4: Commit**

```bash
git add tests/unit/worker/test_shootout_orchestrator.py
git commit -m "test: rewrite test_shootout_orchestrator with real DB fixtures, remove unittest.mock"
```

---

### Task 9: Rewrite remaining worker tests (5 files)

**Files:**
- Modify: `tests/unit/worker/test_gear_sync_consumer.py`
- Modify: `tests/unit/worker/test_gts_admin_cli.py`
- Modify: `tests/unit/worker/test_worker_config.py`
- Modify: `tests/unit/worker/test_entrypoint.py`
- Modify: `tests/unit/worker/test_progress_publisher.py`

**Approach per file:**

- `test_gear_sync_consumer.py`: Already mostly real fixtures. Remove `AsyncMock` import, replace any remaining `AsyncMock()` with real async functions or `monkeypatch.setattr`.
- `test_gts_admin_cli.py`: Replace `MagicMock`/`AsyncMock` for httpx with `httpx.MockTransport`. Replace `patch("...print")` with `capsys`.
- `test_worker_config.py`: Replace `patch.dict(os.environ, ...)` with `monkeypatch.setenv()`.
- `test_entrypoint.py`: Replace `AsyncMock` for subprocess with `monkeypatch.setattr` on the specific functions. For process management tests, create simple async helpers instead of `AsyncMock`.
- `test_progress_publisher.py`: Replace `AsyncMock` for Redis with `monkeypatch.setattr`. Create simple async test doubles (plain functions returning expected values).

**Step 1: Rewrite each file**

For each file, remove `unittest.mock` imports and replace with pytest-native alternatives.

**Step 2: Run all worker tests**

Run: `just tdd tests/unit/worker/`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/unit/worker/
git commit -m "test: remove unittest.mock from all worker tests"
```

---

## Phase 3: Mock Audit — Integration Tests (Priority 2)

### Task 10: Rewrite integration test mocks (5 files)

**Files:**
- Modify: `tests/integration/webapp/test_audit_integration_t117.py`
- Modify: `tests/integration/webapp/test_auth_api_t19.py`
- Modify: `tests/integration/webapp/test_exception_handlers.py`
- Modify: `tests/integration/webapp/test_processing_trigger.py`
- Modify: `tests/integration/webapp/test_t3k_oauth_integration_t15.py`

**Approach per file:**

- `test_audit_integration_t117.py`: Replace `patch("webapp.api.v1.auth.T3KProvider")` with `httpx.MockTransport` or a real test T3K provider fixture. Replace auth file mock with `tmp_path` fixture.
- `test_auth_api_t19.py`: Same — replace T3KProvider mock with `httpx.MockTransport` for the underlying HTTP calls.
- `test_exception_handlers.py`: Replace `patch.dict("os.environ", ...)` with `monkeypatch.setenv()`.
- `test_processing_trigger.py`: Replace `patch("...enqueue_to_worker")` with `monkeypatch.setattr`. The mock here is appropriate in intent (don't actually enqueue) — just use `monkeypatch` instead of `patch`.
- `test_t3k_oauth_integration_t15.py`: Replace `patch("httpx.AsyncClient.post/get")` with `httpx.MockTransport`.

**Step 1: Rewrite each file**

**Step 2: Run integration tests**

Run: `just tdd tests/integration/webapp/`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/integration/webapp/
git commit -m "test: remove unittest.mock from integration tests"
```

---

## Phase 4: Mock Audit — Unit Tests (Priority 3)

### Task 11: Rewrite scheduler test mocks (conftest + 3 files)

**Files:**
- Modify: `tests/unit/scheduler/conftest.py`
- Modify: `tests/unit/scheduler/test_scheduled_tasks.py`
- Modify: `tests/unit/scheduler/test_distributed_lock.py`
- Modify: `tests/unit/scheduler/test_scheduler_config.py`

**Approach:**

- `conftest.py`: Remove `AsyncMock` import. Remove `_fix_redis_mock` autouse fixture entirely. Replace `mock_redis` pattern with real Redis fixture (Redis is always available in Docker).
- `test_scheduled_tasks.py`: Replace `AsyncMock` for lock with a real `DistributedLock` test instance.
- `test_distributed_lock.py`: Replace `AsyncMock(spec=redis.Redis)` with real Redis connection.
- `test_scheduler_config.py`: Replace `patch.dict(os.environ, ...)` with `monkeypatch.setenv()`.

**Step 1: Rewrite each file**
**Step 2: Run scheduler tests**

Run: `just tdd tests/unit/scheduler/`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/unit/scheduler/
git commit -m "test: remove unittest.mock from scheduler tests"
```

---

### Task 12: Rewrite T3K, webapp, and worktree test mocks (8 files)

**Files:**
- Modify: `tests/unit/t3k/test_api_client.py` (already uses MockTransport — just remove unused import if present)
- Modify: `tests/unit/t3k/test_circuit_breaker.py`
- Modify: `tests/unit/webapp/services/test_audit_service.py`
- Modify: `tests/unit/webapp/test_oauth_handler_t11.py`
- Modify: `tests/unit/webapp/test_shutdown.py`
- Modify: `tests/unit/worktree/test_video_docker_checks_t80.py`
- Modify: `tests/unit/worktree/test_video_service_integration_t80.py`
- Modify: `tests/unit/worktree/test_video_health_checks_t80.py`

**Approach per file:**

- `test_api_client.py`: Already clean per agent findings. Verify no `unittest.mock` import.
- `test_circuit_breaker.py`: Replace `AsyncMock()` with simple `async def` test doubles.
- `test_audit_service.py`: Replace `Mock()` repository with a real in-memory implementation or `monkeypatch.setattr`.
- `test_oauth_handler_t11.py`: Replace `patch("httpx.AsyncClient.post/get")` with `httpx.MockTransport`.
- `test_shutdown.py`: Replace `MagicMock` for signal handlers with `monkeypatch.setattr`. Replace `patch("...signal.signal")` with `monkeypatch`. Logger assertions via `caplog` fixture.
- `test_video_docker_checks_t80.py`: Replace `patch("worktree.docker.run_compose")` with `monkeypatch.setattr`. Replace `patch("httpx.get")` with `httpx.MockTransport`. Replace `patch("time.sleep/time.time")` with `monkeypatch`.
- `test_video_service_integration_t80.py`: Replace `patch("socket.socket")` with `monkeypatch.setattr`.
- `test_video_health_checks_t80.py`: Replace all `@patch(...)` decorators with `monkeypatch.setattr`. This is the heaviest — 5+ patches per test method.

**Step 1: Rewrite each file**
**Step 2: Run all remaining tests**

Run: `just tdd tests/unit/t3k/ tests/unit/webapp/ tests/unit/worktree/`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/unit/t3k/ tests/unit/webapp/ tests/unit/worktree/
git commit -m "test: remove unittest.mock from t3k, webapp, and worktree tests"
```

---

## Phase 5: Quality Gate

### Task 13: Add unittest.mock ban to quality gate

**Files:**
- Modify: quality gate configuration (find existing banned-import check)

**Step 1: Find existing enforcement**

Search for existing banned-import patterns in the codebase (ruff rules, custom scripts, pre-commit hooks).

**Step 2: Add `unittest.mock` to banned imports for test files**

Add a ruff rule or custom check that fails if any file in `tests/` imports from `unittest.mock`.

**Step 3: Run full test suite**

Run: `just check`
Expected: ALL PASS, no `unittest.mock` imports detected

**Step 4: Commit**

```bash
git add <quality-gate-files>
git commit -m "build: add unittest.mock ban to quality gate"
```

---

## Phase 6: Final Verification

### Task 14: Full quality gate and push

**Step 1: Run all checks**

Run: `just check`
Expected: ALL PASS (lint, types, tests, import checks)

**Step 2: Push**

```bash
git pull --rebase
git push
```
