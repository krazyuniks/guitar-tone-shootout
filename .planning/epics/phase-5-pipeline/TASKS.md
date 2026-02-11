# E111: Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer

## Overview

Complete the T3K-to-GTS data pipeline end-to-end. All work runs on **main branch** (worker/Redis/scheduler are main-only infrastructure).

**Source-agnostic principle:** T3K is the first source adapter. Admin APIs, CLI, and scheduler abstractions use generic "source" namespace (`/api/admin/sources/{source_name}/...`). T3K-specific code stays in `sources/t3k/`.

## Dependency Graph

```
A1 (dual DB)     A2 (container orch)     A3 (migration)     C1 (sync loop)     C2 (download)
    │                   │                      │                  │                  │
    ├───────────────────┤                      │                  │                  │
    ▼                   ▼                      │                  │                  │
         B1 (admin API)                        │                  │                  │
              │                                │                  │                  │
              ├────────────────────────────────┼──────────────────┘                  │
              │                                │                                     │
              ▼                                ▼                                     │
         F1 (CLI)                    E1 (scheduler)                                  │
                                               │                                     │
    A1 ────────────────────────────────────────┼─────── C1 ────────── C2 ───────────┘
                                               │           │            │
                                               ▼           ▼            ▼
                                                    D1 (consumer + mapper)
```

Waves:
- **Wave 1** (parallel): A1, A2, A3, C1, C2
- **Wave 2** (parallel): B1, D1
- **Wave 3** (parallel): E1, F1

---

### A1: Worker dual database session factory

**Objective:** Extend `worker/db.py` with session factories for both gts_core and gts_t3k_source databases. The pgmq consumer needs to read from gts_t3k_source (pgmq queues, staging data) while writing to gts_core (Gear, GearModel, GearSource). `WorkerSettings.t3k_database_url` already exists but has no factory.

**Citation:** Epic #111 Phase 5D — "Dual database session factory in worker (gts_core write pool + gts_t3k_source read pool)"

**Acceptance Criteria:**
- [ ] `get_core_session()` context manager yields AsyncSession connected to gts_core (refactor existing `get_session` usage)
- [ ] `get_t3k_session()` context manager yields AsyncSession connected to gts_t3k_source
- [ ] Both use the existing engine cache pattern from `async_session_factory()`
- [ ] `get_db_session` FastAPI dependency in admin.py updated to use `get_core_session()`
- [ ] Unit tests verify sessions use correct database URLs

**Scope:**
- Modify: `apps/worker/src/worker/db.py`
- Modify: `apps/worker/src/worker/admin.py`

**Dependencies:** None

**Labels:** `project:worker`, `phase:5A`

---

### A2: Worker container orchestration — run 3 services

**Objective:** Update the worker Docker setup to run admin API (uvicorn on port 8001) + TaskIQ worker + pgmq consumer as concurrent processes from a single container. Currently the worker command is `taskiq worker worker.main:broker --workers 1` which only runs TaskIQ.

**Citation:** Epic #111 Phase 5A — "Update worker Docker Compose command to run all 3 services: admin API (port 8001) + TaskIQ worker + pgmq consumer"

**Acceptance Criteria:**
- [ ] Entrypoint script starts 3 processes: admin API, TaskIQ worker, pgmq consumer
- [ ] Admin API accessible on port 8001 within Docker network
- [ ] TaskIQ worker processes jobs as before
- [ ] pgmq consumer process starts (initial no-op loop until D1 implements it)
- [ ] If any child process exits non-zero, all processes stop (fail-fast)
- [ ] SIGTERM triggers graceful shutdown of all 3 processes
- [ ] docker-compose.yml worker command updated to use entrypoint

**Scope:**
- Create: `apps/worker/src/worker/entrypoint.py`
- Modify: `docker-compose.yml`

**Dependencies:** None

**Labels:** `project:worker`, `phase:5A`

---

### A3: T3K oauth_tokens Alembic migration

**Objective:** Add Alembic migration for the `oauth_tokens` table in gts_t3k_source. The `OAuthToken` ORM model exists in `source_t3k/adapters/outbound/models.py` but has no migration. Required for scheduler auth refresh task (E1).

**Citation:** Epic #111 Phase 5B — "Migration for missing staging tables: oauth_tokens"

**Acceptance Criteria:**
- [ ] Migration creates `oauth_tokens` table with columns: id (serial PK), access_token_encrypted (varchar 1024), refresh_token_encrypted (varchar 1024), expires_at (timestamptz), created_at (timestamptz)
- [ ] Migration is reversible (downgrade drops table)
- [ ] Migration applies cleanly after existing 0001_t3k_staging_tables migration

**Scope:**
- Create: `sources/t3k/alembic/versions/0002_oauth_tokens.py`

**Dependencies:** None

**Labels:** `project:source-t3k`, `phase:5B`

---

### B1: Admin API — enqueue, source dashboard, dead-letter, and lock management

**Objective:** Extend worker admin API with: (1) `POST /api/admin/enqueue` for webapp→worker job dispatch, (2) source-agnostic dashboard endpoints under `/api/admin/sources/{source_name}/` for sync monitoring and control, (3) dead-letter listing and lock management endpoints. Source dashboard uses generic URL namespace — T3K is the first implementation. Unknown source names return 404.

**Citation:** Epic #111 Phase 5A — all admin endpoint gaps listed in Scope section

**Acceptance Criteria:**
- [ ] `POST /api/admin/enqueue` accepts `{"job_id": "uuid"}`, dispatches to TaskIQ broker, returns job detail
- [ ] `GET /api/admin/sources/{source}/sync/status` returns sync state (running/idle), checkpoint info, enabled flag
- [ ] `POST /api/admin/sources/{source}/sync` triggers manual sync, returns 202 Accepted
- [ ] `GET /api/admin/sources/{source}/sync/stats` returns total records synced, queue depths, last sync duration
- [ ] `GET /api/admin/sources/{source}/sync/lag` returns seconds since last successful sync
- [ ] `GET /api/admin/sources/{source}/errors/summary` returns recent error counts by type
- [ ] `GET /api/admin/sources/{source}/auth/status` returns OAuth token validity and expiry
- [ ] `GET /api/admin/jobs/dead-lettered` returns list of dead-lettered jobs
- [ ] `GET /api/admin/jobs/pending-retries/count` returns integer count
- [ ] `POST /api/admin/sources/{source}/sync/unlock` releases distributed sync lock, returns 200
- [ ] `POST /api/admin/scheduler/unlock` releases scheduler lock, returns 200
- [ ] Unknown `{source}` returns 404 with message
- [ ] Pydantic response schemas for all new endpoints

**Scope:**
- Modify: `apps/worker/src/worker/admin.py`
- Modify: `apps/worker/src/worker/schemas.py`

**Dependencies:** A1, A2

**Labels:** `project:worker`, `phase:5A`

---

### C1: Interleaved backfill+newest sync loop

**Objective:** Refactor `T3KSyncService` with a `run_catalog_sync()` method that alternates backfill walk (oldest→newest from checkpoint) + newest check (scan from most recent until hitting already-synced records). Implements skip-recently-synced and stale detection for efficient continuous operation.

**Citation:** Epic #111 Phase 5B — "Interleaved backfill+newest sync loop (run_catalog_sync()) — alternating backfill walk + newest check with skip-recently-synced and stale detection"

**Acceptance Criteria:**
- [ ] `run_catalog_sync()` is the main entry point for continuous sync
- [ ] Alternates between backfill batch (N pages from checkpoint) and newest check (2 pages from newest)
- [ ] Backfill advances checkpoint forward through catalog
- [ ] Newest check stops when hitting records already in staging
- [ ] Records synced within last 7 days are skipped (skip-recently-synced)
- [ ] Checkpoint older than 30 days triggers reset (stale detection)
- [ ] Each batch commits checkpoint for resumability
- [ ] Publishes GearSyncRecord to pgmq via existing GearSyncPublisher after staging

**Scope:**
- Modify: `sources/t3k/src/source_t3k/services/sync_service.py`

**Dependencies:** None

**Labels:** `project:source-t3k`, `phase:5B`

---

### C2: Model file download service

**Objective:** Create service that downloads NAM model files from T3K to local storage at `source_downloads/t3k/{source_uuid}/` with SHA-256 checksum validation. Integrates with sync loop so models are downloaded after pack/model staging.

**Citation:** Epic #111 Phase 5B — "Model file download service — download NAM files to source_downloads/t3k/{source_uuid}, SHA-256 checksum validation"

**Acceptance Criteria:**
- [ ] Downloads model files using `download_url` from T3KModelStaging
- [ ] Stores files at `source_downloads/t3k/{source_record_id}/{filename}`
- [ ] Validates SHA-256 checksum against model's `checksum` field
- [ ] Skips download if file already exists with correct checksum
- [ ] Retries failed downloads up to 3 times with backoff
- [ ] Removes partial/corrupt files on checksum failure
- [ ] Integrated into sync loop — called after model staging

**Scope:**
- Create: `sources/t3k/src/source_t3k/services/model_downloader.py`
- Modify: `sources/t3k/src/source_t3k/services/sync_service.py`

**Dependencies:** None

**Labels:** `project:source-t3k`, `phase:5B`

---

### D1: pgmq consumer and GearMapperService

**Objective:** Build the pgmq consumer polling loop that reads from `gear_pack_sync` and `gear_model_sync` queues in gts_t3k_source, validates messages against GearSyncRecord schema, and upserts to gts_core via GearMapperService. Implements dead-letter handling, file migration, and `pgmq.archive()` on success.

**Citation:** Epic #111 Phase 5D — entire "Consumer Flow" section

**Acceptance Criteria:**
- [ ] Consumer polls `gear_pack_sync` queue using `pgmq.read_with_poll('gear_pack_sync', vt=60, qty=10)`
- [ ] Consumer polls `gear_model_sync` queue
- [ ] Messages deserialised via `GearSyncRecord.from_dict()`
- [ ] Invalid messages (schema validation failure) moved to `sync_dead_letter` queue
- [ ] Messages with `read_ct > 5` moved to `sync_dead_letter` queue
- [ ] GearMapperService creates/updates Gear + GearSource in gts_core using `(source_name, source_record_id)` lookup
- [ ] GearMapperService creates/updates GearModel in gts_core
- [ ] `source_updated_at` comparison for last-write-wins (skip if source_updated_at <= existing)
- [ ] Model files moved from `source_downloads/{source}/{source_record_id}/` to `models/{gear_model_uuid}.nam` within UoW
- [ ] `pgmq.archive(queue_name, msg_id)` called in gts_t3k_source after successful gts_core commit
- [ ] Consumer runs as async loop with 5-second poll interval
- [ ] Consumer handles database connection errors with exponential backoff

**Scope:**
- Create: `apps/worker/src/worker/consumers/gear_sync.py`
- Create: `apps/worker/src/worker/services/gear_mapper.py`

**Dependencies:** A1, C1, C2

**Labels:** `project:worker`, `phase:5D`

---

### E1: Scheduler tasks — SOURCE_SYNC handler, ensure_sync, auth refresh

**Objective:** Create `SOURCE_SYNC` TaskIQ job handler that triggers T3K sync. Add `ensure_source_sync_running` scheduler task (every 5 min) that auto-starts sync if not running. Add T3K auth refresh task (every 12h) that refreshes OAuth tokens and stores them in `oauth_tokens` table.

**Citation:** Epic #111 Phase 5A — "ensure_source_sync_running scheduler task (*/5 min)", "SOURCE_SYNC job handler", "T3K auth refresh scheduled task (every 12h via scheduler)"

**Acceptance Criteria:**
- [ ] `SOURCE_SYNC` TaskIQ job handler creates T3KSyncService and calls `run_catalog_sync()`
- [ ] `ensure_source_sync_running` checks for active sync via Redis lock
- [ ] If no sync running and T3K sync enabled, dispatches `SOURCE_SYNC` job
- [ ] `ensure_source_sync_running` runs every 5 minutes via TaskIQ schedule labels
- [ ] T3K auth refresh task calls OAuth manager's refresh flow
- [ ] Refreshed tokens stored in `oauth_tokens` table (gts_t3k_source)
- [ ] Auth refresh runs every 12 hours via TaskIQ schedule labels
- [ ] `SOURCE_SYNC` registered as JobType enum value

**Scope:**
- Create: `apps/worker/src/worker/jobs/source_sync.py`
- Modify: `apps/scheduler/src/scheduler/schedules/jobs.py`
- Create: `apps/scheduler/src/scheduler/schedules/auth.py`
- Modify: `libs/core/src/core/domain/value_objects/job_status.py`
- Modify: `apps/worker/src/worker/main.py`

**Dependencies:** A3, B1, C1

**Labels:** `project:worker`, `project:scheduler`, `phase:5A`

---

### F1: gts-admin CLI and just admin registration

**Objective:** Create Python CLI that wraps worker admin API HTTP calls. Uses source-agnostic command namespace. Register as `just admin` in justfile.

**Citation:** Epic #111 Phase 5A — "gts-admin Python CLI registered as just admin (commands: t3k-status, t3k-sync, jobs, job-health, unlock-sync, unlock-scheduler)"

**Acceptance Criteria:**
- [ ] `just admin source-status <source>` displays sync status, checkpoint, lag formatted as table
- [ ] `just admin source-sync <source>` triggers manual sync, shows confirmation
- [ ] `just admin jobs [--status=STATUS]` lists jobs in table format
- [ ] `just admin job-health` shows overall health: Redis, DB, uptime, active jobs count
- [ ] `just admin unlock-sync <source>` releases sync lock with confirmation
- [ ] `just admin unlock-scheduler` releases scheduler lock with confirmation
- [ ] CLI uses httpx to call `http://worker:8001` (Docker internal) or `http://localhost:8001` (host)
- [ ] Connection errors produce clear error message ("Worker not reachable — is it running?")
- [ ] `just admin` registered in justfile pointing to `scripts/gts-admin`

**Scope:**
- Create: `scripts/gts-admin`
- Modify: `justfile`

**Dependencies:** B1

**Labels:** `project:tooling`, `phase:5A`
