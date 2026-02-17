# Backup Automation & Mock Audit Design

> **Branch:** `feat/t3k-login-auto-refresh`
> **Date:** 2026-02-17

---

## Task 1: Backup Automation

### 1.1 Backup Infrastructure (`worktree/backup.py`)

Extract backup logic from `worktree/docker.py` into a dedicated module.

**Database discovery:** Query the running PostgreSQL instance directly — no hardcoded database lists.

```sql
SELECT datname FROM pg_database
WHERE datistemplate = false AND datname != 'postgres';
```

This returns `gts_core`, `gts_t3k_source`, and any future source databases.

**Functions:**

- `discover_databases(worktree_path) -> list[str]` — runs the discovery query via `docker compose exec -T db psql`
- `backup_database(worktree_path, db_name) -> Path` — runs `pg_dump -Fc` for one database
- `backup_all_databases(worktree_path) -> list[Path]` — backs up every discovered database
- `get_latest_backup(db_name) -> Path | None` — most recent backup for a specific database
- `get_latest_backups() -> dict[str, Path | None]` — latest backup per database

**Naming:** `{db_name}.{YYYYMMDD_HHMM}.dump` (e.g. `gts_core.20260217_1200.dump`)

**Transport (host):** `docker compose exec -T db pg_dump -Fc -U gts {db_name}` piped to file.

### 1.2 CLI Subcommands

In `worktree/commands/services.py`:

- `./worktree.py backup` — backs up all discovered databases
- `./worktree.py restore <file>` — restores a specific database from a dump file

Justfile aliases:
- `just db-backup` → `./worktree.py backup`
- Update `just db-import` to handle per-database restore

### 1.3 Setup Integration

`worktree/commands/setup.py` — update `_get_or_create_backup` and `_import_database` to use the new multi-database backup/restore functions. Backup before destructive ops, restore after.

### 1.4 Scheduler Integration

**Dockerfile.dev:** Add `postgresql-client` to apt-get install (~5MB). Provides `pg_dump` binary inside the container.

**docker-compose.yml:** Add to scheduler service:
```yaml
volumes:
  - ../backups:/app/backups
```

**New file: `apps/scheduler/src/scheduler/schedules/backup.py`**

- `async def backup_all_databases()` — discovers databases via `psql` connection to `db:5432`, runs `pg_dump -h db -U gts -Fc {db_name}` for each, writes to `/app/backups/`
- Password passed via `PGPASSWORD` env var (parsed from `DATABASE_URL`)
- Schedule: every 12 hours
- Cleanup: delete backups older than 7 days (configurable via `BACKUP_RETENTION_DAYS` env var)

**Transport (Docker):** `pg_dump -h db -U gts -Fc {db_name}` directly (no docker compose exec — already inside the network).

The scheduler and worktree.py implementations are separate — one runs on host (via docker compose exec), the other runs inside Docker (direct pg_dump). Both discover databases the same way.

### 1.5 Health & Status Integration

**`worktree/health.py`** — Add to `HealthCheckResult`:
- `last_backup: dict[str, datetime | None]` — last backup time per database (scanned from `../backups/`)
- `backup_stale: bool` — True if any database's latest backup is older than 24 hours or missing

Backup staleness is a warning, not an unhealthy state.

**`worktree/commands/info.py`** — Add backup section to `status` and `health` output:
```
Backups:
  gts_core:        2h ago (gts_core.20260217_1000.dump, 45MB)
  gts_t3k_source:  2h ago (gts_t3k_source.20260217_1000.dump, 12MB)
```

**`.claude/commands/status.md`** — Add backup info to `/status` skill output.

---

## Task 2: Mock Audit

### Policy

- No `unittest.mock`, `Mock`, `patch`, `MagicMock`, `AsyncMock`
- Test against real services (DB, Redis — always available in Docker)
- External HTTP calls: use `httpx.MockTransport` (httpx's built-in test utility, not unittest.mock)

### Priority Order

**1. Worker tests (28 failures — highest priority):**

| File | Current problem | Fix |
|------|----------------|-----|
| `test_audio_job.py` | Mocked `session.execute` returns wrong types | Real SQLite session, real model objects |
| `test_master_audio.py` | Same | Same |
| `test_shootout_orchestrator.py` | Same | Same |
| `test_gear_sync_consumer.py` | Mocked Redis | Real Redis connection |
| `test_gts_admin_cli.py` | Mocked config/services | Real fixtures |
| `test_worker_config.py` | `patch.dict` for env vars | `monkeypatch.setenv` |
| `test_entrypoint.py` | Mocked startup | Real service init |
| `test_progress_publisher.py` | Mocked Redis pub/sub | Real Redis |

**2. Integration tests (webapp):**

| File | Fix |
|------|-----|
| `test_audit_integration_t117.py` | Remove mock patches, use existing `db_session` fixture |
| `test_auth_api_t19.py` | Same |
| `test_exception_handlers.py` | Same |
| `test_processing_trigger.py` | Same |
| `test_t3k_oauth_integration_t15.py` | Same |

**3. Unit tests (remaining):**

| File | Fix |
|------|-----|
| `tests/unit/scheduler/conftest.py` + 3 tests | Replace `mock_redis`/`AsyncMock` with real Redis |
| `tests/unit/t3k/test_api_client.py` | `httpx.MockTransport` |
| `tests/unit/t3k/test_circuit_breaker.py` | `httpx.MockTransport` |
| `tests/unit/webapp/services/test_audit_service.py` | Real DB session fixtures |
| `tests/unit/webapp/test_oauth_handler_t11.py` | Real DB + `httpx.MockTransport` for T3K |
| `tests/unit/webapp/test_shutdown.py` | Real service lifecycle |
| `tests/unit/worktree/test_video_*.py` (3 files) | Real subprocess/temp directories |

### Quality Gate

After rewriting, add a check that fails on `unittest.mock` imports in test files (extend existing banned-import enforcement).

---

## Key Files

| Area | Files |
|------|-------|
| Backup core | `worktree/backup.py` (new), `worktree/docker.py` (remove old export) |
| Backup CLI | `worktree/commands/services.py` |
| Backup setup | `worktree/commands/setup.py` |
| Scheduler backup | `apps/scheduler/src/scheduler/schedules/backup.py` (new) |
| Scheduler main | `apps/scheduler/src/scheduler/main.py` |
| Docker | `infrastructure/docker/Dockerfile.dev`, `docker-compose.yml` |
| Health | `worktree/health.py`, `worktree/commands/info.py` |
| Status skill | `.claude/commands/status.md` |
| Justfile | `justfile` |
| Tests | 25 test files (see audit list above) |
