# Plan: Epic #117

## Goal

Migrate from monolithic worker with TaskIQ/Redis to event-driven architecture with one container per bounded context, pgmq-only messaging, transactional outbox, and a single consolidated database.

## Observable Truths

1. Running docker compose ps shows t3k-sync, audio-worker, and video-worker containers in healthy state
2. Running docker compose ps does NOT show worker, scheduler, or redis containers
3. Querying the gts_core database shows T3K staging tables (t3k_packs, t3k_models, t3k_creators, etc.) alongside core domain tables
4. The gts_t3k_source database no longer exists on the PostgreSQL server
5. pgmq queues (gear_sync, process_audio, render_video) are visible via SQL query in gts_core
6. The webapp dispatches processing jobs via pgmq command messages instead of TaskIQ
7. T3K sync runs automatically in the t3k-sync container, staging gear data into t3k_* tables
8. All existing integration and unit tests pass against the new single-database architecture
9. just up-d starts the full stack with the new container topology without errors
10. Each BC container exposes a /health endpoint that returns healthy status

## User Journeys

### Journey J1: Developer

Developer starts the stack with just up-d, then runs docker compose ps to observe the new container topology. They see t3k-sync, audio-worker, and video-worker containers running healthily. They verify that the old worker, scheduler, and redis containers are absent.

**Truths covered:** 1, 2, 9
**Entry point:** /
**Critical transitions:**
- stack stopped -> stack running with new topology (just up-d)
- stack running -> container list verified (docker compose ps shows per-BC containers, no legacy containers)

### Journey J2: Developer

Developer connects to the database via just psql. They query \dt t3k_* and see T3K staging tables in gts_core. They attempt to connect to gts_t3k_source and confirm it no longer exists.

**Truths covered:** 3, 4
**Entry point:** /
**Critical transitions:**
- psql connected to gts_core -> t3k tables visible in gts_core (\dt t3k_* shows t3k_packs, t3k_models, etc.)
- t3k tables confirmed -> old database absent (connection to gts_t3k_source refused)

### Journey J3: Developer

Developer queries pgmq queues in gts_core via SQL to verify messaging infrastructure is operational. They see gear_sync, process_audio, and render_video queues listed.

**Truths covered:** 5
**Entry point:** /
**Critical transitions:**
- psql connected to gts_core -> pgmq queues visible (SELECT * FROM pgmq.list_queues() returns gear_sync, process_audio, render_video)

### Journey J4: Developer

Developer triggers a processing job from the webapp. The job is dispatched as a pgmq command message. The audio-worker container picks up the message and processes it. T3K sync runs automatically in the background in t3k-sync container.

**Truths covered:** 6, 7
**Entry point:** /
**Critical transitions:**
- webapp job dispatch -> pgmq command enqueued (webapp publishes ProcessAudioCommand to process_audio queue)
- pgmq command enqueued -> audio processed (audio-worker consumes and processes the command)
- t3k-sync container running -> gear data staged (t3k-sync fetches from API and writes to t3k_* tables)

### Journey J5: Developer

Developer runs the full test suite to verify no regressions from the architecture migration. All unit, integration, and regression tests pass.

**Truths covered:** 8
**Entry point:** /
**Critical transitions:**
- test suite started -> all tests passing (just test exits with code 0)

### Journey J6: Developer

Developer curls the /health endpoint on each BC container to verify all components are operational and reporting healthy status.

**Truths covered:** 10
**Entry point:** /
**Critical transitions:**
- containers running -> all health checks passing (curl /health on t3k-sync, audio-worker, video-worker returns 200 with healthy status)

## Stories

### Story: Single Database Consolidation (`01-database`)

**Purpose:** Merge gts_t3k_source into gts_core with BC-prefixed tables (t3k_*). Remove dual-database configuration. All T3K staging tables live alongside core tables in one database.

**Agent:**
- model: codex
- skills: []
- tools: []
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Create: `infrastructure/migrations/versions/012_merge_t3k_and_bc_prefix.py`
- Create: `scripts/migrate_t3k_data.py`
- Create: `tests/integration/worker/test_single_database.py`
- Modify: `infrastructure/docker/init-core-db.sh`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.override.yml`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/base.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/models.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/repository.py`
- Modify: `apps/worker/src/worker/dependencies.py`
- Modify: `apps/webapp/src/webapp/config/settings.py`
- Modify: `tests/conftest.py`

**Wiki Sections:** Database, Database Separation, Core Database Tables (`gts_core`), Source Database Tables (`gts_t3k_source`), T3K Database Tables, pgmq Integration, Transactional Send

**Implementation Notes:**
- Create Alembic migration 012 that: (a) creates T3K staging tables in gts_core with t3k_ prefix (t3k_packs, t3k_models, t3k_creators, t3k_tags, t3k_makes, t3k_pack_images, t3k_pack_links), (b) adds pgmq extension to gts_core if not present
- Create scripts/migrate_t3k_data.py — idempotent script to copy data from gts_t3k_source to gts_core.t3k_* tables with checkpoint tracking
- Update ALL ORM model files in apps/webapp/src/webapp/adapters/persistence/models/ — not just base.py. Each model's __tablename__ remains unchanged for core tables (no core_ prefix needed since they are the default). Source-specific models use t3k_ prefix.
- Update sources/t3k/src/source_t3k/adapters/outbound/models.py to use t3k_ prefixed table names and connect to gts_core instead of gts_t3k_source
- Update sources/t3k/src/source_t3k/adapters/outbound/repository.py to use gts_core session
- Update init-core-db.sh to include pgmq extension creation and T3K-related setup
- Remove or empty infrastructure/docker/init-t3k-db.sh (mark for deletion — the second database is no longer created)
- In docker-compose.yml remove the T3K database service/volume and T3K-related env vars. Single db service with one database.
- Update apps/worker/src/worker/dependencies.py to use single database session (remove T3K session factory)
- Update apps/worker/src/worker/consumers/gear_sync.py to read from same database
- Update apps/webapp/src/webapp/config/settings.py to remove T3K database URL
- Update tests/conftest.py fixtures to use single database connection
- Update justfile to remove psql-t3k command
- Remove sources/t3k/alembic/ directory (T3K-specific Alembic config no longer needed)
- Write tests/integration/worker/test_single_database.py verifying T3K tables accessible from same connection as core tables

**Truths Addressed:** 3, 4

---

### Validation Checkpoint: After Single Database Consolidation

**Type:** process
**Checks:**
- Alembic migration applies successfully to gts_core (evidence: command, exit_code, output_tail) [cmd: `just migrate`]
- Single database integration test passes — T3K tables queryable from gts_core (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/worker/test_single_database.py`]

---

### Story: Messaging Infrastructure (`02-messaging`)

**Purpose:** Create pgmq wrapper, message envelope schema, command/event types, consumer base class, and transactional outbox. This provides the messaging foundation all BC containers use.

**Agent:**
- model: codex
- skills: []
- tools: []
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Create: `libs/core/src/core/records/envelope.py`
- Create: `libs/core/src/core/records/commands.py`
- Create: `libs/core/src/core/records/events.py`
- Create: `libs/core/src/core/ports/message_bus.py`
- Create: `libs/core/src/core/services/pgmq_client.py`
- Create: `libs/core/src/core/services/consumer_base.py`
- Create: `tests/unit/core/test_messaging.py`
- Modify: `pyproject.toml`
- Modify: `libs/core/pyproject.toml`
- Modify: `libs/core/src/core/records/__init__.py`
- Modify: `libs/core/src/core/ports/__init__.py`
- Modify: `libs/core/src/core/services/__init__.py`

**Wiki Sections:** Message Flow, Command Messages, Event Messages, Message Envelope, Queue Design, pgmq Configuration, Transactional Outbox, Dead Letter Queue, Consumer Pattern, Inter-BC Communication, Domain Event Pattern

**Implementation Notes:**
- The design doc specifies infra/messaging/ as a separate workspace member. For this implementation, messaging infrastructure lives in libs/core alongside existing ports and records, since all BCs already depend on core. A future extraction to a separate package can happen if needed.
- libs/core/src/core/records/envelope.py — MessageEnvelope Pydantic model with message_id (UUIDv7), message_type, source_bc, timestamp, correlation_id, payload dict
- libs/core/src/core/records/commands.py — Command schemas: ProcessAudioCommand, RenderVideoCommand, SyncGearCommand. Each extends MessageEnvelope with typed payload.
- libs/core/src/core/records/events.py — Event schemas: GearSyncedEvent, AudioProcessedEvent, VideoRenderedEvent
- libs/core/src/core/ports/message_bus.py — Protocol for pgmq operations: send, read, archive, create_queue, drop_queue
- libs/core/src/core/services/pgmq_client.py — Async pgmq wrapper implementing MessageBus protocol. Uses raw SQL via SQLAlchemy for pgmq.send(), pgmq.read_with_poll(), pgmq.archive(), pgmq.create(). Handles visibility timeout and batch reads.
- libs/core/src/core/services/consumer_base.py — Abstract consumer base class with: async poll loop, visibility timeout handling, retry with exponential backoff, DLQ routing when read_ct exceeds max retries, graceful shutdown via signal handlers
- Add pgmq queue creation to init-core-db.sh — create queues: gear_sync, process_audio, render_video, and their DLQ counterparts
- Add asyncpg or psycopg as dependency to libs/core/pyproject.toml for raw pgmq SQL operations
- Update pyproject.toml workspace config and import-linter contracts for new modules
- Write tests/unit/core/test_messaging.py — test envelope serialisation, command/event schema validation, consumer retry logic

**Truths Addressed:** 5

---

### Validation Checkpoint: After Messaging Infrastructure

**Type:** process
**Checks:**
- Messaging unit tests pass — envelope serialisation, command/event schemas, consumer logic (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/unit/core/test_messaging.py`]

---

### Story: Per-BC Containers (`03-containers`)

**Purpose:** Create t3k-sync, audio-worker, and video-worker containers. Move sync logic from monolithic worker and scheduler into t3k-sync. Move audio and video processing into their respective workers. Remove the scheduler app.

**Agent:**
- model: codex
- skills: []
- tools: []
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Create: `infrastructure/docker/Dockerfile.t3k-sync`
- Create: `infrastructure/docker/Dockerfile.audio-worker`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.override.yml`
- Modify: `pyproject.toml`
- Modify: `apps/worker/src/worker/main.py`
- Modify: `apps/worker/src/worker/consumers/gear_sync.py`
- Modify: `apps/worker/src/worker/jobs/source_sync.py`

**Wiki Sections:** Container Architecture, Container Topology, Resource Limits, Health Checks, T3K Sync Jobs, Audio Processing Jobs, Video Rendering Jobs, Docker Compose Architecture, Service Topology, Profile System, Continuous Sync

**Implementation Notes:**
- Create apps/t3k_sync/ workspace member: pyproject.toml, src/t3k_sync/__init__.py, src/t3k_sync/main.py (FastAPI with /health endpoint and lifespan startup for consumer + scheduler), src/t3k_sync/consumer.py (pgmq consumer for gear_sync queue using consumer_base from core), src/t3k_sync/scheduler.py (embedded cron-like scheduler for ensure_sync_running, replaces apps/scheduler/). The agent MUST create the apps/t3k_sync/ directory structure.
- Create apps/audio_worker/ workspace member: pyproject.toml, src/audio_worker/__init__.py, src/audio_worker/main.py (FastAPI with /health endpoint and lifespan startup for consumer), src/audio_worker/consumer.py (pgmq consumer for process_audio queue). The agent MUST create the apps/audio_worker/ directory structure.
- Create apps/video_worker/ workspace member: pyproject.toml, src/video_worker/__init__.py, src/video_worker/main.py (FastAPI with /health endpoint and lifespan startup for consumer), src/video_worker/consumer.py (pgmq consumer for render_video queue). The agent MUST create the apps/video_worker/ directory structure.
- Move sync logic from apps/worker/jobs/source_sync.py and apps/scheduler/schedules/source_sync.py into t3k_sync/
- Move audio processing logic from apps/worker/jobs/audio_processing.py into audio_worker/consumer.py
- Move video/shootout job logic from apps/worker/jobs/shootout.py into video_worker/consumer.py
- infrastructure/docker/Dockerfile.t3k-sync — based on Dockerfile.dev pattern, runs t3k_sync app
- infrastructure/docker/Dockerfile.audio-worker — based on Dockerfile.dev pattern, runs audio_worker app
- Video worker extends existing Dockerfile.remotion (already exists) — update docker-compose to wire it
- Add t3k-sync, audio-worker, video-worker services to docker-compose.yml on jobs profile with health checks
- Delete apps/scheduler/ directory entirely — scheduling is now embedded in t3k-sync
- Remove scheduler service from docker-compose.yml
- Update pyproject.toml workspace members to add new apps, remove scheduler
- Remove sync-related code from monolithic worker (jobs/source_sync.py, consumers/gear_sync.py) but keep worker alive for now (removed in Story 04)

**Truths Addressed:** 1, 7, 9, 10

---

### Validation Checkpoint: After Per-BC Containers

**Type:** process
**Checks:**
- Docker services start without errors including new BC containers (evidence: command, exit_code, output_tail) [cmd: `just up-d`]
- Lint and type checks pass with new packages (evidence: command, exit_code, output_tail) [cmd: `just check`]

---

### Story: Webapp pgmq Dispatch and Legacy Removal (`04-webapp-dispatch`)

**Purpose:** Replace TaskIQ job dispatch in webapp with pgmq command publishing. Remove TaskIQ, Redis, and the monolithic worker. Update tooling (justfile, worktree.py) for the new topology.

**Agent:**
- model: codex
- skills: []
- tools: []
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Create: `tests/integration/webapp/test_pgmq_dispatch.py`
- Modify: `apps/webapp/src/webapp/services/job_service.py`
- Modify: `apps/webapp/src/webapp/services/shootout_service.py`
- Modify: `apps/webapp/src/webapp/api/v1/jobs.py`
- Modify: `apps/worker/pyproject.toml`
- Modify: `apps/worker/src/worker/broker.py`
- Modify: `apps/worker/src/worker/tasks.py`
- Modify: `apps/worker/src/worker/task_manager.py`
- Modify: `docker-compose.yml`
- Modify: `justfile`
- Modify: `worktree/docker.py`
- Modify: `worktree/commands/setup.py`

**Wiki Sections:** Job Types, Job Lifecycle, Progress Tracking, Cleanup Targets, Job Scheduling (TaskIQ), Scope Separation, Deployment & Operations

**Implementation Notes:**
- Update apps/webapp/src/webapp/services/job_service.py — replace TaskIQ task dispatch with pgmq command publishing (ProcessAudioCommand, RenderVideoCommand). Import pgmq_client from core.
- Update apps/webapp/src/webapp/services/shootout_service.py — dispatch shootout processing via pgmq commands instead of TaskIQ tasks
- Update apps/webapp/src/webapp/api/v1/jobs.py — replace Redis pub/sub job progress with database polling (query job table status/heartbeat directly)
- Remove TaskIQ: delete or empty apps/worker/src/worker/broker.py, tasks.py, task_manager.py. Remove taskiq dependencies from apps/worker/pyproject.toml.
- Remove Redis: remove redis service from docker-compose.yml and docker-compose.override.yml. Remove Redis connection config from worker.
- Remove or minimise monolithic worker: if all jobs migrated to BC containers, remove worker service from docker-compose.yml. If admin API still needed, refactor to minimal admin-only service.
- Update justfile — remove worker/scheduler/redis commands, add per-BC commands (logs-t3k-sync, logs-audio-worker, shell-audio-worker, etc.)
- Update worktree/docker.py — update service topology for new containers, remove references to old worker/scheduler/redis
- Update worktree/commands/setup.py — remove T3K database creation, Redis setup. Single database only.
- Write tests/integration/webapp/test_pgmq_dispatch.py — test webapp sends pgmq command and it appears in queue

**Truths Addressed:** 2, 6

---

### Validation Checkpoint: After Webapp pgmq Dispatch and Legacy Removal

**Type:** process
**Checks:**
- Webapp pgmq dispatch integration test passes (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_pgmq_dispatch.py`]
- Docker services start without redis or old worker (evidence: command, exit_code, output_tail) [cmd: `just up-d`]

---

### Story: Quality Gates, Tests, and Documentation (`05-quality-docs`)

**Purpose:** Run full test suite against new architecture, fix any failures, update AGENTS.md and architecture documentation to reflect the new event-driven topology.

**Agent:**
- model: codex
- skills: []
- tools: []
- max_turns: 30
- max_budget_usd: 3.0

**Scope:**
- Modify: `AGENTS.md`
- Modify: `pyproject.toml`
- Modify: `tests/conftest.py`
- Modify: `infrastructure/docker/init-core-db.sh`

**Wiki Sections:** Testing Strategy, Docker Compose Architecture, Migration Path, Phase Summary

**Implementation Notes:**
- Run just check (lint + types + imports) and fix any failures from the migration
- Run just test and fix any broken tests — update fixtures, imports, and database connection configs as needed
- Update AGENTS.md to reflect new architecture: container topology (t3k-sync, audio-worker, video-worker), no scheduler/redis/monolithic worker, single database, pgmq messaging
- Update import-linter contracts in pyproject.toml for new packages (t3k_sync, audio_worker, video_worker)
- Update tests/conftest.py if any remaining dual-database references exist
- Verify init-core-db.sh creates pgmq queues correctly
- Update .claude/skills/gts-architecture/references/job-scheduling.md and infrastructure.md to reflect new topology
- Run just test-regression, just test-unit, just test-integration to verify full suite passes

**Truths Addressed:** 8

---

### Validation Checkpoint: After Quality Gates, Tests, and Documentation

**Type:** quality
**Checks:**
- Full quality gate passes (lint, types, import contracts) (evidence: command, exit_code, output_tail) [cmd: `just check`]
- All unit tests pass (evidence: command, exit_code, output_tail) [cmd: `just test-unit`]
- All integration tests pass (evidence: command, exit_code, output_tail) [cmd: `just test-integration`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. Running docker compose ps shows t3k-sync, audio-worker, and video-worker containers in healthy state | `infrastructure/docker/Dockerfile.t3k-sync`, `infrastructure/docker/Dockerfile.audio-worker`, `docker-compose.yml` (+5 more) | Per-BC Containers |
| 2. Running docker compose ps does NOT show worker, scheduler, or redis containers | `tests/integration/webapp/test_pgmq_dispatch.py`, `apps/webapp/src/webapp/services/job_service.py`, `apps/webapp/src/webapp/services/shootout_service.py` (+9 more) | Webapp pgmq Dispatch and Legacy Removal |
| 3. Querying the gts_core database shows T3K staging tables (t3k_packs, t3k_models, t3k_creators, etc.) alongside core domain tables | `infrastructure/migrations/versions/012_merge_t3k_and_bc_prefix.py`, `scripts/migrate_t3k_data.py`, `tests/integration/worker/test_single_database.py` (+9 more) | Single Database Consolidation |
| 4. The gts_t3k_source database no longer exists on the PostgreSQL server | `infrastructure/migrations/versions/012_merge_t3k_and_bc_prefix.py`, `scripts/migrate_t3k_data.py`, `tests/integration/worker/test_single_database.py` (+9 more) | Single Database Consolidation |
| 5. pgmq queues (gear_sync, process_audio, render_video) are visible via SQL query in gts_core | `libs/core/src/core/records/envelope.py`, `libs/core/src/core/records/commands.py`, `libs/core/src/core/records/events.py` (+9 more) | Messaging Infrastructure |
| 6. The webapp dispatches processing jobs via pgmq command messages instead of TaskIQ | `tests/integration/webapp/test_pgmq_dispatch.py`, `apps/webapp/src/webapp/services/job_service.py`, `apps/webapp/src/webapp/services/shootout_service.py` (+9 more) | Webapp pgmq Dispatch and Legacy Removal |
| 7. T3K sync runs automatically in the t3k-sync container, staging gear data into t3k_* tables | `infrastructure/docker/Dockerfile.t3k-sync`, `infrastructure/docker/Dockerfile.audio-worker`, `docker-compose.yml` (+5 more) | Per-BC Containers |
| 8. All existing integration and unit tests pass against the new single-database architecture | `AGENTS.md`, `pyproject.toml`, `tests/conftest.py` (+1 more) | Quality Gates, Tests, and Documentation |
| 9. just up-d starts the full stack with the new container topology without errors | `infrastructure/docker/Dockerfile.t3k-sync`, `infrastructure/docker/Dockerfile.audio-worker`, `docker-compose.yml` (+5 more) | Per-BC Containers |
| 10. Each BC container exposes a /health endpoint that returns healthy status | `infrastructure/docker/Dockerfile.t3k-sync`, `infrastructure/docker/Dockerfile.audio-worker`, `docker-compose.yml` (+5 more) | Per-BC Containers |
