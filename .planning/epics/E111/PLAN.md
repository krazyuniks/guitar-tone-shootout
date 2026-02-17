# Plan: Epic #111

## Goal

The T3K-to-GTS data pipeline works end-to-end: worker container runs admin API + TaskIQ + pgmq consumer, T3K sync fetches and downloads gear with interleaved backfill+newest, pgmq consumer upserts to gts_core, and the gts-admin CLI provides operational visibility.

## Observable Truths

1. The worker container starts and runs all 3 services simultaneously: admin API on port 8001, TaskIQ worker, and pgmq consumer.
2. GET /health on the worker (port 8001) returns a composite health status showing admin_api, taskiq_broker, and pgmq_consumer component statuses.
3. POST /api/admin/enqueue with a job type and parameters creates a job record and returns job details with a PENDING status.
4. GET /api/admin/t3k/sync/status returns the current sync state including pagination checkpoint and running status.
5. POST /api/admin/t3k/sync triggers a catalog sync job and returns a 202 Accepted with the created job ID.
6. GET /api/admin/t3k/sync/stats returns pack and model counts from the T3K staging database.
7. GET /api/admin/t3k/auth/status returns the OAuth token validity and expiry information.
8. GET /api/admin/jobs/dead-lettered returns a list of jobs that have exceeded max retry attempts.
9. T3K sync runs an interleaved loop alternating between backfill (oldest→newest from checkpoint) and newest checks, skipping recently-synced items.
10. Model files download to source_downloads/t3k/{source_uuid}/ with SHA-256 checksum validation, rejecting files that fail verification.
11. The pgmq consumer polls the gear_sync queue in gts_t3k_source using pgmq.read_with_poll with a 60-second visibility timeout and batch size of 10.
12. After the consumer processes a GearSyncRecord message, a corresponding Gear and GearModel record exists in gts_core with the correct source attribution.
13. Messages whose read_ct exceeds the max retry threshold are moved to the gear_sync_dlq queue and archived from the main gear_sync queue.
14. Running 'just admin t3k-status' calls the worker admin API and prints a formatted dashboard showing sync state, stats, and auth status.
15. Running 'just admin jobs' calls the worker admin API and prints a formatted list of jobs with their status, type, and timestamps.

## User Journeys

### Journey J1: Platform operator

The operator starts the worker container and checks health. They verify the composite health endpoint shows all 3 services running. They enqueue a test job via POST /api/admin/enqueue and confirm it appears in the job list. They check dead-lettered jobs to ensure no stuck work. Finally, they use 'just admin jobs' and 'just admin t3k-status' to get a quick operational dashboard.

**Truths covered:** 1, 2, 3, 8, 14, 15
**Entry point:** http://localhost:8001/health
**Critical transitions:**
- Worker container startup -> Health endpoint responds (Docker compose starts worker with multi-service command)
- Health endpoint -> Enqueue endpoint (POST /api/admin/enqueue with job_type and params)
- Enqueue response -> Job list (GET /api/admin/jobs shows new job)
- Terminal -> CLI output (just admin jobs and just admin t3k-status)

### Journey J2: Platform operator managing T3K sync

The operator checks T3K auth status to verify OAuth tokens are valid. They check sync status to see the current checkpoint. They review sync stats to see how many packs/models are staged. They trigger a sync via POST, which starts the interleaved backfill+newest loop. The sync fetches gear metadata from the T3K API and downloads model files with checksum validation to source_downloads/t3k/.

**Truths covered:** 4, 5, 6, 7, 9, 10
**Entry point:** http://localhost:8001/api/admin/t3k/auth/status
**Critical transitions:**
- Auth status check -> Sync status check (GET /api/admin/t3k/sync/status)
- Sync status -> Sync stats (GET /api/admin/t3k/sync/stats)
- Sync stats review -> Trigger sync (POST /api/admin/t3k/sync)
- Sync triggered -> SOURCE_SYNC job runs (TaskIQ dispatches job, sync service runs interleaved loop)
- Sync service fetches metadata -> Model files downloaded (model_downloader downloads NAM files with SHA-256 check)

### Journey J3: Automated system (pgmq consumer)

After T3K sync stages gear records and publishes GearSyncRecord messages to the gear_sync pgmq queue, the consumer polls the queue. It validates each message against the GearSyncRecord schema, checks that model files exist, then upserts Gear + GearModel into gts_core within a UoW transaction. On success, it archives the message. If a message has been read too many times (read_ct > max_retries), it moves the message to gear_sync_dlq instead.

**Truths covered:** 11, 12, 13
**Entry point:** pgmq gear_sync queue in gts_t3k_source
**Critical transitions:**
- gear_sync queue -> Consumer reads message (pgmq.read_with_poll('gear_sync', vt=60, qty=10))
- Message read -> DLQ check (Check read_ct > max_retries threshold)
- DLQ check passed -> Gear upsert in gts_core (GearMapperService upserts with (source_name, source_record_id, source_updated_at))
- Successful upsert -> Message archived (pgmq.archive('gear_sync', msg_id))
- DLQ check failed -> Message moved to DLQ (Insert into gear_sync_dlq, archive from gear_sync)

## Stories

### Story: Worker Docker Wiring & Dual Database (`01-docker-wiring-and-dual-db`)

**Purpose:** Update worker Docker Compose command to run all 3 services (admin API + TaskIQ + pgmq consumer), add dual database session factory (gts_core write + gts_t3k_source read), add T3K staging migration for missing tables, and update composite health endpoint.

**Agent:**
- model: sonnet
- skills: [gts-architecture, docker-infra, gts-backend-dev]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Create: `sources/t3k/alembic/versions/003_add_missing_staging_tables.py`
- Modify: `docker-compose.yml`
- Modify: `apps/worker/src/worker/main.py`
- Modify: `apps/worker/src/worker/db.py`
- Modify: `apps/worker/src/worker/config.py`
- Modify: `apps/worker/src/worker/health.py`
- Modify: `apps/worker/pyproject.toml`

**Wiki Sections:** GTS-Technical-Architecture :: architecture-layers, GTS-Technical-Architecture :: data-ingestion, GTS-Technical-Architecture :: persistence, GTS-Technical-Architecture :: infrastructure, IMPLEMENTATION :: phase-5a-job-system, IMPLEMENTATION :: phase-5d-pgmq-consumer

**Implementation Notes:**
- Worker command must start 3 processes: uvicorn for admin API, taskiq worker, and the pgmq consumer loop. Use a Python entry point script or supervisord-style approach.
- db.py needs dual session factories: get_core_session() for gts_core (write) and get_t3k_session() for gts_t3k_source (read). Use separate async engines.
- config.py needs T3K_SOURCE_DATABASE_URL in addition to existing DATABASE_URL.
- health.py composite health must report admin_api, taskiq_broker, pgmq_consumer statuses.
- T3K migration 003 adds: t3k_tags, t3k_makes, t3k_pack_images, t3k_pack_links, oauth_tokens tables to gts_t3k_source.
- Worker pyproject.toml may need pgmq/psycopg dependencies for direct pgmq SQL queries.
- Docker compose worker service needs T3K_SOURCE_DATABASE_URL environment variable.
- Use asyncio to run admin API + consumer loop concurrently; TaskIQ worker may need subprocess.

**Truths Addressed:** 1, 2

---

### Validation Checkpoint: After Worker Docker Wiring & Dual Database

**Type:** process
**Checks:**
- Worker container starts successfully with all 3 services (admin API, TaskIQ, pgmq consumer) (evidence: process_name, pid_or_status, log_excerpt)
- GET /health on port 8001 returns 200 with composite status showing admin_api, taskiq_broker, and pgmq_consumer (evidence: process_name, pid_or_status, log_excerpt)
- T3K staging migration 003 applies successfully adding missing tables (evidence: process_name, pid_or_status, log_excerpt)

---

### Story: Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks (`02-admin-api-endpoints`)

**Purpose:** Extend worker admin API with all Phase 5A endpoints: POST /api/admin/enqueue, T3K sync/auth/error endpoints, dead-lettered jobs, pending retries count, lock management, and ensure_source_sync_running scheduler task.

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, web-handlers, gts-architecture, service-patterns]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 45
- max_budget_usd: 5.0

**Scope:**
- Create: `apps/worker/src/worker/jobs/source_sync.py`
- Modify: `apps/worker/src/worker/admin.py`
- Modify: `apps/worker/src/worker/services/admin_service.py`
- Modify: `apps/worker/src/worker/jobs/registry.py`
- Modify: `apps/worker/src/worker/jobs/handlers.py`
- Modify: `apps/scheduler/src/scheduler/schedules/jobs.py`
- Modify: `apps/scheduler/src/scheduler/schedules/auth.py`
- Modify: `libs/core/src/core/domain/value_objects/job_types.py`

**Wiki Sections:** GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: data-ingestion, GTS-Technical-Architecture :: auth, IMPLEMENTATION :: phase-5a-job-system, IMPLEMENTATION :: phase-5b-t3k-source

**Implementation Notes:**
- POST /api/admin/enqueue takes {job_type, params} and creates Job + dispatches via TaskIQ.
- T3K endpoints query gts_t3k_source via the dual session factory from story 01.
- GET /api/admin/t3k/sync/status: query checkpoint table for last sync position + check Redis lock for running status.
- GET /api/admin/t3k/sync/stats: SELECT COUNT(*) from packs, models in gts_t3k_source.
- GET /api/admin/t3k/sync/lag: time delta between now and last checkpoint update.
- GET /api/admin/t3k/auth/status: read OAuth token from gts_t3k_source, check expiry.
- GET /api/admin/t3k/errors/summary: aggregate errors by type from jobs table.
- POST /api/admin/t3k/sync: create SOURCE_SYNC job + dispatch to TaskIQ.
- GET /api/admin/jobs/dead-lettered: filter jobs where status=DEAD.
- GET /api/admin/jobs/pending-retries/count: count jobs where status=RETRY.
- POST /api/admin/t3k/sync/unlock: release Redis sync lock.
- POST /api/admin/scheduler/unlock: release Redis scheduler lock.
- SOURCE_SYNC job handler in source_sync.py: acquires sync lock, instantiates T3K sync service, runs sync, releases lock.
- ensure_source_sync_running scheduler task: check env SYNC_ENABLED, check Redis lock, if not running create SOURCE_SYNC job.
- T3K auth refresh in auth.py: refresh OAuth token every 12h.
- Add SOURCE_SYNC to JobType enum in core value objects if not present.

**Truths Addressed:** 2, 3, 4, 5, 6, 7, 8

---

### Validation Checkpoint: After Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks

**Type:** api+response
**Checks:**
- POST /api/admin/enqueue returns 201 with created job details (evidence: status_code, url, method, response_body_excerpt)
- GET /api/admin/t3k/sync/status returns 200 with sync state (evidence: status_code, url, method, response_body_excerpt)
- GET /api/admin/t3k/auth/status returns 200 with token info (evidence: status_code, url, method, response_body_excerpt)
- GET /api/admin/jobs/dead-lettered returns 200 with list (evidence: status_code, url, method, response_body_excerpt)

---

### Story: T3K Interleaved Sync Loop & Model Downloader (`03-t3k-sync-and-download`)

**Purpose:** Complete the T3K sync service with interleaved backfill+newest loop and implement the model file download service with SHA-256 checksum validation.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, service-patterns, error-handling]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Modify: `sources/t3k/src/source_t3k/services/sync_service.py`
- Modify: `sources/t3k/src/source_t3k/services/model_downloader.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/sync_record_mapper.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/pgmq_publisher.py`
- Modify: `sources/t3k/src/source_t3k/domain/checkpoints.py`

**Wiki Sections:** GTS-Technical-Architecture :: data-ingestion, IMPLEMENTATION :: phase-5b-t3k-source, REFERENCE-ARCHITECTURE :: data-ingestion-pipeline

**Implementation Notes:**
- run_catalog_sync() implements the interleaved loop: alternate between backfill_walk() and newest_check().
- Backfill walk: page through catalog oldest→newest from checkpoint, persist each page, update checkpoint.
- Newest check: scan from newest until hitting items already synced within skip threshold (7 days).
- Stale detection: if checkpoint is too old (configurable threshold), reset to page 1.
- Skip recently synced: items with sync timestamp within threshold are skipped.
- After staging each item: map to GearSyncRecord via sync_record_mapper, publish via pgmq_publisher.
- Model downloader: download NAM files to source_downloads/t3k/{source_uuid}/, compute SHA-256 hash of downloaded file, compare against expected hash from API.
- Reject and log files that fail checksum verification.
- GearSyncRecord is published only after files are validated (sync_ready state).
- Use httpx for file downloads with streaming to avoid memory issues on large files.
- Checkpoint updates must be atomic with staging writes (same transaction).

**Truths Addressed:** 9, 10

---

### Story: pgmq Consumer & GearMapper Service (`04-pgmq-consumer-and-gear-mapper`)

**Purpose:** Implement the pgmq consumer polling loop that reads from gear_sync queue, validates messages, upserts to gts_core via GearMapperService, handles dead letter queue, and archives processed messages.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, service-patterns, repository-patterns, error-handling]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 45
- max_budget_usd: 5.0

**Scope:**
- Modify: `apps/worker/src/worker/consumers/gear_sync.py`
- Modify: `apps/worker/src/worker/services/gear_mapper.py`
- Modify: `apps/worker/src/worker/main.py`

**Wiki Sections:** GTS-Technical-Architecture :: data-ingestion, GTS-Technical-Architecture :: persistence, GTS-Technical-Architecture :: design-patterns, IMPLEMENTATION :: phase-5d-pgmq-consumer, REFERENCE-ARCHITECTURE :: data-ingestion-pipeline

**Implementation Notes:**
- Consumer polling loop: async loop calling pgmq.read_with_poll('gear_sync', vt=60, qty=10) using raw SQL via the t3k session.
- For each message: check read_ct > MAX_RETRIES (3). If exceeded, move to gear_sync_dlq and archive from gear_sync.
- Validate message payload against GearSyncRecord Pydantic model.
- Verify model file exists at source_downloads/t3k/{source_uuid}/.
- GearMapperService.upsert(): within a UoW transaction on gts_core: INSERT or UPDATE Gear + GearModel using (source_name, source_record_id, source_updated_at) as idempotency key. Last-write-wins by source_updated_at.
- File migration: move file from source_downloads/{source}/{source_uuid} to models/{core_uuid}.nam within the same transaction scope.
- On success: pgmq.archive('gear_sync', msg_id) in gts_t3k_source.
- Consumer must handle connection errors gracefully with backoff.
- pgmq SQL: SELECT * FROM pgmq.read_with_poll('gear_sync', 60, 10, 1000) — last param is poll_timeout_ms.
- DLQ SQL: SELECT pgmq.send('gear_sync_dlq', msg::jsonb); SELECT pgmq.archive('gear_sync', msg_id);
- The gear_sync_dlq queue must be created — add to init-pgmq.sql or create in consumer startup.
- GearSource record links Gear to source via (source_name, source_record_id, source_updated_at).
- Integrate consumer loop startup into worker main.py (called from story 01's multi-service runner).

**Truths Addressed:** 11, 12, 13

---

### Validation Checkpoint: After pgmq Consumer & GearMapper Service

**Type:** quality
**Checks:**
- just check passes (lint, types, import contracts) (evidence: commands_run, exit_code, error_count)

---

### Story: gts-admin CLI, just Commands & Tests (`05-admin-cli-and-tests`)

**Purpose:** Create the gts-admin Python CLI that calls worker admin API, register it as 'just admin', and write unit/integration tests for the new worker endpoints, consumer, and sync service.

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, gts-testing, gts-architecture]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Create: `scripts/gts-admin`
- Modify: `justfile`
- Modify: `tests/unit/worker/test_admin_endpoints.py`
- Modify: `tests/unit/worker/test_gear_mapper.py`
- Modify: `tests/unit/worker/test_consumer.py`

**Wiki Sections:** GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: infrastructure, IMPLEMENTATION :: phase-5a-job-system, Development-Guide :: testing

**Implementation Notes:**
- scripts/gts-admin is a Python CLI (use argparse or typer with PEP 723 inline deps) that calls worker admin API via httpx.
- Commands: t3k-status (calls /api/admin/t3k/sync/status + /stats + /auth/status, formats as dashboard), t3k-sync (POST /api/admin/t3k/sync), jobs (GET /api/admin/jobs), job-health (GET /health), unlock-sync (POST /api/admin/t3k/sync/unlock), unlock-scheduler (POST /api/admin/scheduler/unlock).
- just admin recipe: delegates to scripts/gts-admin with args.
- Make scripts/gts-admin executable with #!/usr/bin/env -S python3 -u shebang.
- Unit tests for admin endpoints: test each route returns correct response codes.
- Unit tests for gear_mapper: test idempotent upsert logic, last-write-wins.
- Unit tests for consumer: test DLQ routing, message validation, archive flow.
- Tests run in Docker via just tdd. Follow existing test patterns.
- Update existing test files if they exist, create new ones if not.

**Truths Addressed:** 14, 15

---

### Validation Checkpoint: After gts-admin CLI, just Commands & Tests

**Type:** regression
**Checks:**
- just test-regression passes (evidence: test_command, exit_code, test_count, failure_count)
- Unit tests for worker admin, consumer, and gear mapper pass (evidence: test_command, exit_code, test_count, failure_count)
- just check passes (lint, types, import contracts) (evidence: commands_run, exit_code, error_count)

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. The worker container starts and runs all 3 services simultaneously: admin API on port 8001, TaskIQ worker, and pgmq consumer. | `sources/t3k/alembic/versions/003_add_missing_staging_tables.py`, `docker-compose.yml`, `apps/worker/src/worker/main.py` (+4 more) | Worker Docker Wiring & Dual Database |
| 2. GET /health on the worker (port 8001) returns a composite health status showing admin_api, taskiq_broker, and pgmq_consumer component statuses. | `sources/t3k/alembic/versions/003_add_missing_staging_tables.py`, `docker-compose.yml`, `apps/worker/src/worker/main.py` (+12 more) | Worker Docker Wiring & Dual Database, Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 3. POST /api/admin/enqueue with a job type and parameters creates a job record and returns job details with a PENDING status. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 4. GET /api/admin/t3k/sync/status returns the current sync state including pagination checkpoint and running status. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 5. POST /api/admin/t3k/sync triggers a catalog sync job and returns a 202 Accepted with the created job ID. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 6. GET /api/admin/t3k/sync/stats returns pack and model counts from the T3K staging database. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 7. GET /api/admin/t3k/auth/status returns the OAuth token validity and expiry information. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 8. GET /api/admin/jobs/dead-lettered returns a list of jobs that have exceeded max retry attempts. | `apps/worker/src/worker/jobs/source_sync.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/services/admin_service.py` (+5 more) | Admin API Endpoints — Enqueue, T3K, Dead Letter, Locks |
| 9. T3K sync runs an interleaved loop alternating between backfill (oldest→newest from checkpoint) and newest checks, skipping recently-synced items. | `sources/t3k/src/source_t3k/services/sync_service.py`, `sources/t3k/src/source_t3k/services/model_downloader.py`, `sources/t3k/src/source_t3k/adapters/outbound/sync_record_mapper.py` (+2 more) | T3K Interleaved Sync Loop & Model Downloader |
| 10. Model files download to source_downloads/t3k/{source_uuid}/ with SHA-256 checksum validation, rejecting files that fail verification. | `sources/t3k/src/source_t3k/services/sync_service.py`, `sources/t3k/src/source_t3k/services/model_downloader.py`, `sources/t3k/src/source_t3k/adapters/outbound/sync_record_mapper.py` (+2 more) | T3K Interleaved Sync Loop & Model Downloader |
| 11. The pgmq consumer polls the gear_sync queue in gts_t3k_source using pgmq.read_with_poll with a 60-second visibility timeout and batch size of 10. | `apps/worker/src/worker/consumers/gear_sync.py`, `apps/worker/src/worker/services/gear_mapper.py`, `apps/worker/src/worker/main.py` | pgmq Consumer & GearMapper Service |
| 12. After the consumer processes a GearSyncRecord message, a corresponding Gear and GearModel record exists in gts_core with the correct source attribution. | `apps/worker/src/worker/consumers/gear_sync.py`, `apps/worker/src/worker/services/gear_mapper.py`, `apps/worker/src/worker/main.py` | pgmq Consumer & GearMapper Service |
| 13. Messages whose read_ct exceeds the max retry threshold are moved to the gear_sync_dlq queue and archived from the main gear_sync queue. | `apps/worker/src/worker/consumers/gear_sync.py`, `apps/worker/src/worker/services/gear_mapper.py`, `apps/worker/src/worker/main.py` | pgmq Consumer & GearMapper Service |
| 14. Running 'just admin t3k-status' calls the worker admin API and prints a formatted dashboard showing sync state, stats, and auth status. | `scripts/gts-admin`, `justfile`, `tests/unit/worker/test_admin_endpoints.py` (+2 more) | gts-admin CLI, just Commands & Tests |
| 15. Running 'just admin jobs' calls the worker admin API and prints a formatted list of jobs with their status, type, and timestamps. | `scripts/gts-admin`, `justfile`, `tests/unit/worker/test_admin_endpoints.py` (+2 more) | gts-admin CLI, just Commands & Tests |
