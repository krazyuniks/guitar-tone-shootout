# Task Breakdown: E94 — Phase 5A/5B/5C Job System, T3K Source Adapter, Shootout Audio

## Dependency Graph

```
A1 (unblocked)
A1 → A2
A1 → A3
A2, A3 → A4

B1 (unblocked)
B1 → B2
B1 → B3
B2 → B4
B2, B3, B4 → B5
B1, B2 → B6

C1 (unblocked)
C1 → C2
A2 → C2

D1 (unblocked)
D1, A2 → D2
D2, C2 → D3
D3 → D4
D4 → D5

A3, A4 → E1

E1, D5, B5, B6 → F1
```

---

### A1: Worker Redis Broker + Settings

**Objective:** Replace the InMemoryBroker in worker with a Redis-backed TaskIQ broker. Create Pydantic settings for worker configuration (REDIS_URL, DATABASE_URL, T3K_DATABASE_URL). Worker container must start successfully with the new broker.

**Citation:** Epic #94 Phase 5A: "Redis broker configuration for TaskIQ"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/config.py` contains `WorkerSettings(BaseSettings)` with `redis_url`, `database_url`, `t3k_database_url` fields
- [ ] `apps/worker/src/worker/main.py` creates `ListQueueBroker` from `taskiq-redis` instead of `InMemoryBroker`
- [ ] Broker connects to Redis using URL from settings
- [ ] Worker starts successfully inside Docker container (verified by container health)
- [ ] Unit test verifies settings load from environment variables
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/config.py`
- Modify: `apps/worker/src/worker/main.py`
- Modify: `apps/worker/src/worker/__init__.py`
- Create: `tests/unit/worker/test_worker_config.py`

**Dependencies:** None

**Labels:** `project:worker`

---

### A2: Worker Database Session Factory

**Objective:** Create an async SQLAlchemy session factory for the worker to access the gts_core database. The worker needs to read/write Job records, Shootout status, and AudioSegment data. Follow the same session pattern as webapp but as a standalone factory (worker is not a FastAPI app for DB access).

**Citation:** Epic #94 Phase 5A: "Worker DB access: gts_core (read/write)"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/db.py` provides `async_session_factory()` and `get_session()` async context manager
- [ ] Session connects to `gts_core` database using `DATABASE_URL` from WorkerSettings
- [ ] Session uses `AsyncSession` with `asyncpg` driver
- [ ] Integration test verifies session can query the jobs table
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/db.py`
- Create: `tests/integration/worker/test_worker_db.py`

**Dependencies:** A1

**Labels:** `project:worker`

---

### A3: Worker Admin API Scaffold

**Objective:** Add a FastAPI application to the worker container serving on port 8001. The Admin API provides health check and will host job management endpoints. No authentication — access is controlled at the network level (port not exposed publicly). Update the Docker compose command to run both the Admin API server and TaskIQ worker.

**Citation:** Epic #94 Phase 5A: "Worker services: Admin API (8001) + TaskIQ worker + pgmq consumer — single container, three responsibilities"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/admin.py` contains a FastAPI application
- [ ] `GET /health` returns 200 with worker status (Redis connection, DB connection, worker uptime)
- [ ] Admin API serves on port 8001
- [ ] `apps/worker/src/worker/main.py` updated: starts both Uvicorn (Admin API) and TaskIQ worker as concurrent async tasks
- [ ] Docker compose command updated to use new entry point
- [ ] Integration test verifies `/health` endpoint responds
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/admin.py`
- Modify: `apps/worker/src/worker/main.py`
- Modify: `docker-compose.yml` (worker service command)
- Create: `tests/integration/worker/test_admin_health.py`

**Dependencies:** A1

**Labels:** `project:worker`

---

### A4: Admin API Job Management Endpoints

**Objective:** Add job management endpoints to the Worker Admin API. These endpoints allow admin operations: listing jobs, viewing details with children, cancelling, and retrying jobs. Uses the worker's own database session (not webapp's).

**Citation:** Epic #94 Phase 5A: "Admin API endpoints: job management, health check"

**Acceptance Criteria:**
- [ ] `GET /api/admin/jobs` lists jobs with optional `status` and `job_type` query filters
- [ ] `GET /api/admin/jobs/{job_id}` returns job details including child jobs
- [ ] `POST /api/admin/jobs/{job_id}/cancel` cancels an active job (returns 409 if already terminal)
- [ ] `POST /api/admin/jobs/{job_id}/retry` retries a failed/dead-lettered job (resets to PENDING)
- [ ] All endpoints return appropriate HTTP status codes (200, 404, 409)
- [ ] No authentication on any endpoint
- [ ] Integration tests for each endpoint
- [ ] `just check` passes

**Scope:**
- Modify: `apps/worker/src/worker/admin.py`
- Create: `apps/worker/src/worker/schemas.py`
- Create: `tests/integration/worker/test_admin_jobs.py`

**Dependencies:** A2, A3

**Labels:** `project:worker`

---

### B1: T3K Domain Model

**Objective:** Define the T3K-specific domain entities and value objects. These represent gear data as it exists in the Tone3000 system, before transformation to GTS format. Entities live in the T3K source adapter package, NOT in core.

**Citation:** Epic #94 Phase 5B: "T3K domain model: T3KPack, T3KModel, T3KCreator (in sources/t3k/, NOT in core)"

**Acceptance Criteria:**
- [ ] `T3KPack` dataclass: `id`, `name`, `slug`, `creator_id`, `description`, `thumbnail_url`, `platform`, `pack_type`, `created_at`, `updated_at`
- [ ] `T3KModel` dataclass: `id`, `pack_id`, `name`, `filename`, `file_size`, `download_url`, `checksum`, `created_at`, `updated_at`
- [ ] `T3KCreator` dataclass: `id`, `username`, `display_name`, `avatar_url`, `profile_url`
- [ ] Value objects for T3K-specific enums: `T3KPlatform`, `T3KPackType`
- [ ] All entities are frozen dataclasses with slots
- [ ] Unit tests for entity creation and validation
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/domain/entities.py`
- Create: `sources/t3k/src/source_t3k/domain/value_objects.py`
- Modify: `sources/t3k/src/source_t3k/domain/__init__.py`
- Create: `tests/unit/t3k/test_t3k_domain.py`

**Dependencies:** None

**Labels:** `project:t3k`

---

### B2: T3K Staging Tables + Alembic Migration

**Objective:** Create SQLAlchemy ORM models for T3K staging tables in the gts_t3k_source database. Set up Alembic configuration for the T3K source database (separate from the gts_core migrations). Create initial migration with staging tables for packs, models, creators, and sync checkpoints.

**Citation:** Epic #94 Phase 5B: "Staging tables: T3K-specific schema in gts_t3k_source (Alembic migrations in source package)"

**Acceptance Criteria:**
- [ ] `sources/t3k/src/source_t3k/adapters/outbound/models.py` contains ORM models: `T3KPackStaging`, `T3KModelStaging`, `T3KCreatorStaging`, `SyncCheckpoint`
- [ ] Separate Alembic configuration at `sources/t3k/alembic.ini` targeting `T3K_DATABASE_URL`
- [ ] Initial migration creates all staging tables in `gts_t3k_source`
- [ ] `SyncCheckpoint` model tracks: `source_name`, `entity_type`, `last_synced_at`, `last_record_id`, `total_synced`
- [ ] ORM models map to/from T3K domain entities
- [ ] Migration runs successfully against gts_t3k_source database
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/adapters/outbound/models.py`
- Create: `sources/t3k/alembic.ini`
- Create: `sources/t3k/alembic/env.py`
- Create: `sources/t3k/alembic/versions/0001_t3k_staging_tables.py`
- Create: `tests/integration/t3k/test_t3k_models.py`

**Dependencies:** B1

**Labels:** `project:t3k`

---

### B3: T3K API Client + Rate Limiting

**Objective:** Build an async HTTP client for the Tone3000 REST API using httpx. Implement per-endpoint rate limiting and a circuit breaker to handle API failures gracefully. The client returns T3K domain entities.

**Citation:** Epic #94 Phase 5B: "Inbound adapter: T3K API client with rate limiting, circuit breaker"

**Acceptance Criteria:**
- [ ] `sources/t3k/src/source_t3k/adapters/inbound/api_client.py` provides `T3KAPIClient` class
- [ ] Methods: `get_packs(page, per_page)`, `get_pack(pack_id)`, `get_models(pack_id)`, `get_creators(page, per_page)`
- [ ] Rate limiter: configurable per-endpoint limits (e.g., 10 req/s for list, 30 req/s for detail)
- [ ] Circuit breaker: opens after N consecutive failures, half-open after timeout, closes on success
- [ ] Returns T3K domain entities (T3KPack, T3KModel, T3KCreator)
- [ ] Raises `T3KAPIError` for non-retriable failures, `T3KRateLimitError` for rate limit hits
- [ ] Unit tests with mocked httpx responses (T3K API is external — mock is correct here)
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/adapters/inbound/api_client.py`
- Create: `sources/t3k/src/source_t3k/adapters/inbound/rate_limiter.py`
- Create: `sources/t3k/src/source_t3k/adapters/inbound/circuit_breaker.py`
- Create: `sources/t3k/src/source_t3k/adapters/inbound/exceptions.py`
- Modify: `sources/t3k/src/source_t3k/adapters/inbound/__init__.py`
- Create: `tests/unit/t3k/test_api_client.py`
- Create: `tests/unit/t3k/test_rate_limiter.py`
- Create: `tests/unit/t3k/test_circuit_breaker.py`

**Dependencies:** B1

**Labels:** `project:t3k`

---

### B4: T3K OAuth Token Management

**Objective:** Implement OAuth token management for authenticating with the Tone3000 API. Tokens are encrypted at rest using Fernet. Token refresh is automatic on 401 responses. Token state is persisted in the gts_t3k_source database.

**Citation:** Epic #94 Phase 5B: "T3K OAuth tokens: Encrypted at rest (Fernet), refreshed automatically"

**Acceptance Criteria:**
- [ ] `sources/t3k/src/source_t3k/adapters/inbound/oauth.py` provides `T3KOAuthManager` class
- [ ] Fernet encryption for access_token and refresh_token at rest
- [ ] `OAuthToken` staging table: `access_token_encrypted`, `refresh_token_encrypted`, `expires_at`, `created_at`
- [ ] `get_valid_token()` returns decrypted token, refreshes if expired
- [ ] `refresh_token()` calls T3K OAuth endpoint, persists new tokens
- [ ] Encryption key from environment variable (`T3K_TOKEN_ENCRYPTION_KEY`)
- [ ] Unit tests for encrypt/decrypt, token expiry check
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/adapters/inbound/oauth.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/models.py` (add OAuthToken model)
- Create: `tests/unit/t3k/test_oauth.py`

**Dependencies:** B2

**Labels:** `project:t3k`

---

### B5: T3K Sync Service — Backfill + Newest Algorithm

**Objective:** Implement the sync service that orchestrates data synchronisation from T3K API to staging tables. Uses a dual-strategy approach: backfill (paginate from oldest) for initial population, and newest (check since last checkpoint) for incremental updates. Checkpoint persistence ensures resume after crash.

**Citation:** Epic #94 Phase 5B: "Sync service: Continuous sync with backfill + newest algorithm, checkpoint persistence"

**Acceptance Criteria:**
- [ ] `sources/t3k/src/source_t3k/services/sync_service.py` provides `T3KSyncService` class
- [ ] `sync_packs()`: fetches packs from T3K API, upserts into staging tables
- [ ] `sync_models()`: fetches models for each pack, upserts into staging tables
- [ ] Backfill strategy: paginate through all records from checkpoint, update checkpoint after each page
- [ ] Newest strategy: check for records updated since last checkpoint
- [ ] Checkpoint persisted via `SyncCheckpoint` model — survives crash/restart
- [ ] Sync runs as a long-lived async task, not a one-shot
- [ ] Unit tests with mocked API client and database (sync logic is testable in isolation)
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/services/sync_service.py`
- Modify: `sources/t3k/src/source_t3k/services/__init__.py`
- Create: `tests/unit/t3k/test_sync_service.py`

**Dependencies:** B2, B3, B4

**Labels:** `project:t3k`

---

### B6: GearSyncRecord pgmq Publisher

**Objective:** Implement the outbound adapter that converts T3K staging records to GearSyncRecord format (from `libs/core/records/`) and publishes them to pgmq queues in gts_t3k_source. Transactional send: stage + enqueue in a single database transaction.

**Citation:** Epic #94 Phase 5B: "Outbound adapter: GearSyncRecord publisher to pgmq (gear_sync queue in gts_t3k_source)"

**Acceptance Criteria:**
- [ ] `sources/t3k/src/source_t3k/adapters/outbound/publisher.py` provides `GearSyncPublisher` class
- [ ] `publish_pack(pack: T3KPackStaging)` converts to GearSyncRecord and enqueues to `gear_pack_sync` queue
- [ ] `publish_model(model: T3KModelStaging)` converts to GearSyncRecord and enqueues to `gear_model_sync` queue
- [ ] Transactional: staging record update + pgmq enqueue in same database transaction
- [ ] Uses `pgmq-sqlalchemy` for queue operations
- [ ] GearSyncRecord payload includes all fields needed for gts_core Gear creation/update
- [ ] Integration test verifies messages appear in pgmq queue
- [ ] `just check` passes

**Scope:**
- Create: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/__init__.py`
- Create: `tests/integration/t3k/test_publisher.py`

**Dependencies:** B1, B2

**Labels:** `project:t3k`

---

### C1: Extend JobType Enum + Shootout Job Types

**Objective:** Add SHOOTOUT (parent orchestrator) and SHOOTOUT_AUDIO (per-chain processing) to the JobType enum in core domain. These new types support the parent/child job hierarchy for shootout processing.

**Citation:** Epic #94 Phase 5A: "Job types: SHOOTOUT, SHOOTOUT_AUDIO"

**Acceptance Criteria:**
- [ ] `JobType.SHOOTOUT` added with value `"shootout"` — parent orchestrator job
- [ ] `JobType.SHOOTOUT_AUDIO` added with value `"shootout_audio"` — per-chain audio processing
- [ ] Existing job types unchanged (AUDIO_PROCESSING, VIDEO_COMPOSITION, GEAR_SYNC, etc.)
- [ ] Domain Job entity correctly handles new types (no code changes needed — enum extension only)
- [ ] ORM Job model stores new enum values correctly (EnumByValue pattern)
- [ ] Unit test verifies new types work in Job state machine transitions
- [ ] `just check` passes

**Scope:**
- Modify: `libs/core/src/core/domain/value_objects/job_status.py`
- Create: `tests/unit/core/test_shootout_job_types.py`

**Dependencies:** None

**Labels:** `project:core`

---

### C2: Shootout Processing Orchestrator Job Handler

**Objective:** Implement the SHOOTOUT job handler in the worker. This is the parent orchestrator: given a shootout ID, it loads the shootout with all chains, creates a child SHOOTOUT_AUDIO job for each chain, and tracks aggregate progress. Updates shootout status from PENDING → RUNNING.

**Citation:** Epic #94 Phase 5C: "Shootout processing orchestrator: Parent job spawning per-chain audio jobs"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/jobs/shootout.py` provides `handle_shootout_job(job_id: UUID)` TaskIQ task
- [ ] Loads shootout from gts_core database with all chains (joinedload)
- [ ] Creates one SHOOTOUT_AUDIO child job per chain (parent_job_id set to parent)
- [ ] Each child job has `entity_id` set to the shootout chain ID
- [ ] Updates parent job progress based on children completion count
- [ ] Updates shootout status: PENDING → RUNNING on start
- [ ] Updates shootout status: RUNNING → COMPLETED when all children complete
- [ ] Updates shootout status: RUNNING → FAILED if any child fails
- [ ] Registers task with TaskIQ broker
- [ ] Unit test with mocked database verifies job creation logic
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/jobs/shootout.py`
- Modify: `apps/worker/src/worker/jobs/__init__.py`
- Modify: `apps/worker/src/worker/main.py` (register task)
- Create: `tests/unit/worker/test_shootout_orchestrator.py`

**Dependencies:** C1, A2

**Labels:** `project:worker`

---

### D1: Scheduler Redis Broker + Distributed Lock

**Objective:** Replace the InMemoryBroker in scheduler with the shared Redis broker. Implement a distributed lock using Redis to ensure only one scheduler instance runs cron tasks at a time. Lock uses 60s TTL with periodic heartbeat renewal.

**Citation:** Epic #94 Phase 5A: "Scheduler container: Distributed lock, cron triggers" and "Scheduler locking: Redis distributed lock (60s TTL, heartbeat renewal)"

**Acceptance Criteria:**
- [ ] `apps/scheduler/src/scheduler/config.py` contains `SchedulerSettings(BaseSettings)` with `redis_url`
- [ ] `apps/scheduler/src/scheduler/main.py` uses Redis broker (same broker URL as worker)
- [ ] `apps/scheduler/src/scheduler/lock.py` implements `DistributedLock` class
- [ ] Lock uses Redis SET NX with 60s TTL
- [ ] Heartbeat renews lock every 30s (async background task)
- [ ] Only the lock holder executes scheduled tasks
- [ ] Graceful release on shutdown
- [ ] Unit test verifies lock acquire/release/heartbeat
- [ ] `just check` passes

**Scope:**
- Create: `apps/scheduler/src/scheduler/config.py`
- Create: `apps/scheduler/src/scheduler/lock.py`
- Modify: `apps/scheduler/src/scheduler/main.py`
- Modify: `apps/scheduler/src/scheduler/__init__.py`
- Create: `tests/unit/scheduler/test_distributed_lock.py`

**Dependencies:** None

**Labels:** `project:scheduler`

---

### D2: Scheduled Tasks — Stale Job Monitor + Retry Processing

**Objective:** Define the scheduled cron tasks that run in the scheduler container. These tasks monitor job health: detect stale (crashed) jobs via heartbeat checks, process pending retries with exponential backoff, and run periodic cleanup.

**Citation:** Epic #94 Phase 5A: "Scheduled tasks: sync monitoring, stale job detection, retry processing, orphan cleanup"

**Acceptance Criteria:**
- [ ] `apps/scheduler/src/scheduler/schedules/jobs.py` defines scheduled tasks using TaskIQ labels
- [ ] `monitor_stale_jobs` (every 2 min): finds jobs with `last_heartbeat` older than 2 minutes while status is RUNNING, marks as DEAD_LETTERED
- [ ] `process_pending_retries` (every 2 min): finds FAILED jobs with `attempt < max_attempts` and `next_retry_at <= now`, resets to PENDING
- [ ] `scheduler_heartbeat` (every 1 min): updates scheduler health record, renews distributed lock
- [ ] Each task uses worker database session to query/update jobs
- [ ] Unit tests verify task logic (stale detection, retry scheduling)
- [ ] `just check` passes

**Scope:**
- Create: `apps/scheduler/src/scheduler/schedules/jobs.py`
- Modify: `apps/scheduler/src/scheduler/schedules/__init__.py`
- Create: `apps/scheduler/src/scheduler/db.py`
- Create: `tests/unit/scheduler/test_scheduled_tasks.py`

**Dependencies:** D1, A2

**Labels:** `project:scheduler`

---

### D3: Per-Chain Audio Processing Job Handler

**Objective:** Implement the SHOOTOUT_AUDIO job handler. Given a shootout chain ID, loads the DI track and signal chain, processes the DI audio through the chain using ChainExecutor from `libs/audio`, saves the output as FLAC, and creates an AudioSegment record with loudness metadata.

**Citation:** Epic #94 Phase 5C: "Per-chain audio processing: DI track through signal chain (NAM + IR + effects via libs/audio)"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/jobs/audio.py` provides `handle_shootout_audio_job(job_id: UUID)` TaskIQ task
- [ ] Loads shootout chain, signal chain (with blocks + user gear), and DI track from database
- [ ] Reads DI audio file from uploads volume
- [ ] Processes through `execute_signal_chain()` from `libs/audio`
- [ ] Saves output as FLAC to `processed_data` volume at `processed/{shootout_id}/{chain_id}.flac`
- [ ] Measures loudness (integrated LUFS + peak dBFS) using `measure_loudness()`
- [ ] Creates `AudioSegment` record in database with file_path, duration, loudness metrics
- [ ] Updates job progress (0 → 50 loading, 50 → 90 processing, 90 → 100 saving)
- [ ] Sends heartbeat updates every 30s during processing
- [ ] Unit test with mocked audio processing verifies job flow
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/jobs/audio.py`
- Modify: `apps/worker/src/worker/jobs/__init__.py`
- Modify: `apps/worker/src/worker/main.py` (register task)
- Create: `tests/unit/worker/test_audio_job.py`

**Dependencies:** D2, C2

**Labels:** `project:worker`

---

### D4: Loudness Normalisation + Master Audio Creation

**Objective:** After all per-chain audio jobs complete, the parent SHOOTOUT job normalises all audio segments to EBU R128 (-14.0 LUFS) for fair A/B comparison, then concatenates them into a master audio file with chapter markers.

**Citation:** Epic #94 Phase 5C: "Loudness normalisation: EBU R128 across all segments" and "Master audio creation: Concatenated segments with chapter markers"

**Acceptance Criteria:**
- [ ] `apps/worker/src/worker/jobs/master_audio.py` provides `create_master_audio(shootout_id: UUID)` function
- [ ] Loads all AudioSegment records for the shootout
- [ ] Normalises each segment to -14.0 LUFS using `normalize_loudness()` from `libs/audio`
- [ ] Updates AudioSegment records with post-normalisation loudness values
- [ ] Concatenates normalised segments in chain position order
- [ ] Adds chapter markers (metadata) for each segment boundary
- [ ] Saves master audio as FLAC at `processed/{shootout_id}/master.flac`
- [ ] Updates shootout `output_path` with master audio location
- [ ] Called by the parent SHOOTOUT orchestrator after all children complete
- [ ] Unit test verifies normalisation and concatenation logic
- [ ] `just check` passes

**Scope:**
- Create: `apps/worker/src/worker/jobs/master_audio.py`
- Modify: `apps/worker/src/worker/jobs/shootout.py` (call master_audio after children complete)
- Create: `tests/unit/worker/test_master_audio.py`

**Dependencies:** D3

**Labels:** `project:worker`

---

### D5: Processing Trigger Endpoint

**Objective:** Add a user-facing endpoint on webapp that triggers shootout processing. The endpoint creates a SHOOTOUT Job in gts_core, then sends an HTTP POST to the worker Admin API to enqueue the TaskIQ task. Returns the job ID so the client can track progress.

**Citation:** Epic #94 Phase 5A: "Webapp integration: trigger processing via HTTP POST to worker admin API" and Phase 5C: "Processing trigger endpoint: POST /api/v1/shootouts/{id}/process"

**Acceptance Criteria:**
- [ ] `POST /api/v1/shootouts/{shootout_id}/process` on webapp
- [ ] Requires `CurrentUser` authentication
- [ ] Validates shootout exists and is owned by current user (404 if not)
- [ ] Validates shootout has at least one chain (400 if empty)
- [ ] Validates shootout status is DRAFT (400 if already processing/completed)
- [ ] Creates Job with `job_type=SHOOTOUT`, `entity_id=shootout.id`, `user_id=current_user.id`
- [ ] Updates shootout status to PENDING
- [ ] Sends HTTP POST to worker Admin API (`http://worker:8001/api/admin/enqueue`) with job ID
- [ ] Returns 202 with `{ "job_id": "..." }`
- [ ] Integration test verifies endpoint creates job and updates shootout status
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Create: `apps/webapp/src/webapp/services/processing_service.py`
- Modify: `apps/worker/src/worker/admin.py` (add `/api/admin/enqueue` endpoint)
- Create: `tests/integration/webapp/test_processing_trigger.py`

**Dependencies:** D4

**Labels:** `project:webapp`

---

### E1: WebSocket Job Progress Endpoint

**Objective:** Add a WebSocket endpoint on webapp that delivers real-time job progress updates to clients. Uses Redis pub/sub: worker publishes progress updates to a Redis channel, webapp subscribes and forwards to connected WebSocket clients.

**Citation:** Epic #94 Phase 5A: "WebSocket progress endpoint (Redis pub/sub → client)" and "Progress reporting: Redis pub/sub → WebSocket"

**Acceptance Criteria:**
- [ ] `apps/webapp/src/webapp/api/v1/ws.py` provides WebSocket endpoint at `/ws/jobs/{job_id}`
- [ ] Requires authentication via query parameter token (`?token=...`)
- [ ] Subscribes to Redis channel `job_progress:{job_id}`
- [ ] Forwards progress messages to WebSocket client as JSON: `{ "progress": 50, "status": "running", "message": "Processing chain 2/5" }`
- [ ] Worker publishes progress updates to Redis channel during job execution
- [ ] `apps/worker/src/worker/progress.py` provides `publish_progress(job_id, progress, status, message)` helper
- [ ] Connection closes when job reaches terminal state
- [ ] Handles client disconnect gracefully
- [ ] Unit test verifies pub/sub message format
- [ ] `just check` passes

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/ws.py`
- Modify: `apps/webapp/src/webapp/main.py` (mount WebSocket route)
- Create: `apps/worker/src/worker/progress.py`
- Modify: `apps/worker/src/worker/jobs/shootout.py` (publish progress)
- Modify: `apps/worker/src/worker/jobs/audio.py` (publish progress)
- Create: `tests/unit/worker/test_progress_publisher.py`

**Dependencies:** A3, A4

**Labels:** `project:webapp`

---

### F1: Integration Smoke Test + Quality Gates

**Objective:** Verify the complete end-to-end flow: webapp triggers processing → worker creates jobs → audio processes → segments stored → master audio created → status updated. All quality gates must pass.

**Citation:** Epic #94 Testing Strategy: "Golden path: just test-golden-path must pass before completion"

**Acceptance Criteria:**
- [ ] All containers start successfully (webapp, worker, scheduler, redis, db)
- [ ] Worker Admin API responds on port 8001
- [ ] Scheduler acquires distributed lock
- [ ] `just check` passes (lint + types)
- [ ] `just test-regression` passes
- [ ] `just test-golden-path` passes
- [ ] No import-linter violations (dependency rules enforced)
- [ ] Worker logs show no unhandled exceptions at startup

**Scope:**
- Create: `tests/integration/worker/test_smoke.py`
- No other file changes (this task verifies everything works together)

**Dependencies:** E1, D5, B5, B6

**Labels:** `project:worker`
