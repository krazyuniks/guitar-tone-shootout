# Context: Phase 5 Pipeline (Epic #111)

## Epic

Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer (5A/5B/5D)

Complete the T3K-to-GTS data pipeline: fix job system runtime wiring (5A), finish T3K source adapter with interleaved sync (5B), and build the pgmq consumer that upserts to gts_core (5D).

## Architecture References

- IMPLEMENTATION.md: Phases 5A (Partial), 5B (Partial), 5D (Pending)
- GTS-Technical-Architecture.md: Domain model, data ingestion pipeline, pgmq consumer, job scheduling

## Current Codebase State

### Worker (apps/worker/)

**Exists:**
- `admin.py` — FastAPI admin API (health, jobs CRUD, cancel, retry). Endpoints: `/health`, `/api/admin/jobs`, `/api/admin/jobs/{id}`, `/api/admin/jobs/{id}/cancel`, `/api/admin/jobs/{id}/retry`
- `main.py` — TaskIQ broker (ListQueueBroker via Redis), imports shootout job handlers
- `db.py` — Single-database session factory (gts_core only). Engine cache with SQLite test support
- `config.py` — WorkerSettings: redis_url, database_url, t3k_database_url (t3k_database_url exists but no dual-session factory)
- `jobs/shootout.py` — SHOOTOUT job handler (parent job dispatcher)
- `jobs/audio.py` — SHOOTOUT_AUDIO job handler (per-chain audio)
- `jobs/master_audio.py` — Master audio creation
- `progress.py` — Redis pub/sub progress publisher
- `schemas.py` — JobSummary, JobDetail Pydantic models
- `consumers/__init__.py` — Empty (no consumer implementations)

**Missing:**
- Worker compose command only runs `taskiq worker` — needs admin API + TaskIQ + pgmq consumer
- `POST /api/admin/enqueue` endpoint
- T3K admin endpoints (status, sync trigger, stats, lag, errors, auth status)
- Dead-lettered/pending-retries admin endpoints
- Lock management admin endpoints
- `ensure_source_sync_running` scheduler task
- `SOURCE_SYNC` job handler
- pgmq consumer loop (gear_sync)
- Dual database session factory (gts_core write + gts_t3k_source read)
- GearMapperService (GearSyncRecord -> Gear upsert)
- gts-admin CLI

### T3K Source Adapter (sources/t3k/)

**Exists:**
- `domain/entities.py` — T3KPack, T3KModel, T3KCreator dataclasses
- `domain/value_objects.py` — T3KPlatform, T3KPackType enums
- `adapters/inbound/api_client.py` — T3K API client
- `adapters/inbound/rate_limiter.py` — Rate limiter
- `adapters/inbound/circuit_breaker.py` — Circuit breaker
- `adapters/inbound/oauth.py` — OAuth manager (Fernet)
- `adapters/outbound/models.py` — T3KPackStaging, T3KModelStaging, T3KCreatorStaging, SyncCheckpoint ORM models
- `adapters/outbound/publisher.py` — GearSyncPublisher (creates GearSyncRecord, uses pgmq.send())
- `services/sync_service.py` — T3KSyncService with backfill/newest strategies, checkpoint management

**Missing:**
- Migration for additional staging tables (t3k_tags, t3k_makes, t3k_pack_images, t3k_pack_links, oauth_tokens)
- Interleaved backfill+newest sync loop (`run_catalog_sync()`)
- Model file download service (NAM file download + checksum)
- T3K auth refresh scheduled task

### Scheduler (apps/scheduler/)

**Exists:**
- `schedules/jobs.py` — monitor_stale_jobs (2min), process_pending_retries (2min), scheduler_heartbeat (1min)

**Missing:**
- `ensure_source_sync_running` task (5min interval)
- T3K auth refresh task (12h interval)

### Core Domain (libs/core/)

**Exists:**
- `records/gear_sync.py` — GearSyncRecord (frozen dataclass): source_name, source_record_id, source_updated_at, operation (CREATE/UPDATE/DELETE), payload dict
- Domain entities: User, Gear, DITrack, SignalChain, Shootout, Job, SignalChainGroup, BlockType

### Docker Compose

- Worker command: `["taskiq", "worker", "worker.main:broker", "--workers", "1"]` — only TaskIQ
- Worker has T3K_DATABASE_URL env var already configured
- Worker volumes: apps/worker, sources (read-only), upload_data, processed_data
- Jobs profile: worker + scheduler

## Dual Database Architecture

- **gts_core** (PostgreSQL) — unified domain model (Gear, User, etc.)
- **gts_t3k_source** (PostgreSQL) — T3K staging tables + pgmq queues
- pgmq extension installed in gts_t3k_source
- Queues: `gear_sync` (main), `gear_sync_dlq` (dead letter)
- Transactional send: source writes + pgmq enqueue in same transaction

## Key Contract

`GearSyncRecord` (libs/core/records/gear_sync.py) is the boundary contract:
- Published by source adapters (T3K → pgmq in gts_t3k_source)
- Consumed by worker pgmq consumer (gts_t3k_source → gts_core)
- Idempotent: (source_name, source_record_id, source_updated_at) last-write-wins
