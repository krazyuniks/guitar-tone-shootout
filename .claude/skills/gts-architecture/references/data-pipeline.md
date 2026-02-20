# Data Ingestion Pipeline

Source adapters are separate workspace members (`sources/*/`), decoupled from webapp.

## Flow

**Incremental Sync:**

1. **Source adapter** fetches changes from external API
2. **Source adapter** persists durable record to source database (staging/audit log)
3. **Source adapter** publishes sync record to message queue (same transaction as step 2)
4. **Core consumer** (t3k-sync container) reads from queue
5. **Core consumer** validates against `GearSyncRecord` schema and upserts to unified Gear model

**Bulk Reingest:**

1. Source adapter replays historical records from its durable staging store
2. Records emitted in batches via the bulk ingestion interface
3. Core applies idempotent upserts and records replay checkpoints

## Topics

One topic per aggregate (not per source):
```
gear_sync
```

Source identity embedded in record payload (`source_name` field).

Other aggregates (User, DITrack, SignalChain, Shootout) are user-created within GTS, not synced from external sources.

## Source Adapters

| Source | Description |
|--------|-------------|
| Tone3000 | NAM captures and IRs (largest volume) |
| AIDA-X | AIDA-X model marketplace (future) |

Community-uploaded IRs use `IRUploadService` in the webapp directly -- they don't go through the sync pipeline.

Each source is a self-contained bounded context:

| Component | Responsibility |
|-----------|----------------|
| Domain models | Source-specific data model |
| Inbound adapters | Fetch from external API/feed |
| Outbound adapters | Map to core schema, send sync records |
| Sync service | Orchestrate incremental sync |
| File service | Download and validate physical files |
| Reingest service | Orchestrate bulk replay |

## Continuous Sync

Each source runs a single continuous sync job that:

1. **Backfill walk** -- Pages through catalog oldest->newest from checkpoint
2. **Newest check** -- Periodically scans from newest until hitting existing items
3. **Skip recently synced** -- Items synced within threshold (e.g., 7 days) are skipped
4. **Stale detection** -- If checkpoint is too old (container was down), reset to page 1

The two algorithms "meet in the middle" for complete catalog coverage while catching new uploads quickly.

## Transactional Send

When source database and pgmq share PostgreSQL:
- Source write + queue publish in same transaction
- No outbox pattern required

When queue is external (future scaling), an outbox pattern preserves atomicity between data persistence and message publication.

## Idempotency

Upsert with `(source_name, source_record_id, source_updated_at)`:
- Last-write-wins by source timestamp
- Safe under replay
- Duplicates are possible (at-least-once delivery); consumers must be idempotent

## Consistency Model

- Delivery is **at-least-once**; duplicates are possible
- Core upserts are idempotent and safe under replay
- System state is **eventually consistent**
- Acceptable lag defined per source via SLOs (typical: seconds to minutes)

## Checkpoint Management

**Incremental Sync Checkpoints:**
- Store `last_synced_at` or `last_source_id` per source
- Sync job resumes from checkpoint on restart
- Updated atomically after successful batch processing

**Reingest Checkpoints:**
- Track progress through bulk reingest (last processed batch/offset)
- Enables resume after failure without restarting from beginning
- Cleared on successful completion

**Consumer Checkpoints:**
- Consumers track message offset via pgmq `read_ct` and archive operations
- On restart, resume from last acknowledged message

## Bulk Ingest Interface

Core provides a bulk ingest interface for replay, migration, and recovery:
- Idempotent upsert using `(source_name, source_record_id, source_updated_at)` for conflict resolution
- Returns per-batch outcomes (inserted, updated, failed) and supports partial retries
- Last-write-wins by source timestamp prevents stale replays overwriting newer data
- Rate limited per source (batch size limit, payload size limit)

## Physical File Ingestion

Physical file ingestion is owned by source adapters. Synchronisation records are emitted **only after** all required files are durably stored and validated.

**File ingest state model:**

```
metadata_fetched -> files_downloading -> files_validated -> sync_ready
```

Source adapters provide recovery jobs to reconcile metadata with stored files and clean up orphans. Files are stored in `source_downloads/{source}/{source_uuid}/` until consumed by the t3k-sync container, which moves them to `models/{core_uuid}.nam`.

## Source Sync Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    t3k-sync container                              │
│  Self-driven polling loop                                        │
│  - Check if sync enabled (env var)                               │
│  - Continuous sync with configurable interval                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SOURCE_SYNC (t3k-sync)                         │
│  1. Acquire sync lock (DB advisory lock)                         │
│  2. Fetch gear + metadata from external API                      │
│  3. Download models to source_downloads/{source}/{source_uuid}   │
│  4. Stage gear record in source DB                               │
│  5. Enqueue GearSyncRecord to pgmq (same transaction as step 4)  │
│  6. Update checkpoint                                            │
│  7. Release lock                                                 │
│  8. Sleep until next iteration                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    pgmq Consumer (t3k-sync)                       │
│  1. Consume message from pgmq                                    │
│  2. Validate GearSyncRecord schema                               │
│  3. Verify model file exists in source_downloads/                │
│  4. Begin UoW transaction:                                       │
│     a. Insert Gear + GearModel in gts_core (core UUIDv7)         │
│     b. Move file to models/{core_uuid}.nam                       │
│     c. Commit                                                    │
│  5. Archive pgmq message                                         │
└──────────────────────────────────────────────────────────────────┘
```

## Data Quality & Validation

### Source Validation

Source adapters validate required fields before emitting sync records:
- Required fields present and non-null
- Field types and ranges correct
- File integrity verified (checksums match)

Invalid records are rejected or quarantined with reason before reaching the queue.

### Core Validation

Core enforces schema validation on ingest:
- `GearSyncRecord` validated against Pydantic schema
- Required fields enforced
- Referential integrity checked

### Quality Metrics

Data quality metrics tracked per source:

| Metric | Purpose |
|--------|---------|
| Null rates on required fields | Detect source data degradation |
| Range checks on numeric fields | Catch invalid values |
| Distribution drift detection | Alert on unexpected data patterns |
| Pass/fail ratios on validation rules | Track overall quality trend |

### Quarantine

Records failing validation are quarantined for investigation:
- Quarantine includes original payload and failure reason
- Reprocessing workflow for fixed records
- Dead-letter queue for messages that fail after max retries

## Consistency & Concurrency

### Data-Level Concurrency

Idempotent upsert with timestamp handles concurrent writes safely. Last-write-wins by source timestamp. No optimistic locking required for sync records because source timestamps provide natural ordering.

For user-created entities (signal chains, shootouts), standard database-level isolation (READ COMMITTED) provides sufficient concurrency control.

### Job-Level Concurrency

Single container per source. Overlapping runs prevented via PostgreSQL advisory locks.

**Future optimisation path:** For high-volume backfills, internal parallelism (concurrent processing within a single container) or source partitioning into multiple containers can increase throughput without sacrificing ordering guarantees.

### Orchestration Control

Both sides of ingestion are managed internally. Complex operations (migrations, recovery) follow defined sequences documented in runbooks.

## Retention & Lifecycle

### Retention Policies

| Data | Retention | Rationale |
|------|-----------|-----------|
| Source staging data | 90 days | Debugging, reingest capability |
| Core domain data | Indefinite | Primary application data |
| Sync audit logs | 1 year | Compliance, debugging |
| Queue messages | Until consumed + 7 days archive | Recovery capability |
| Checkpoints | 30 days | Sufficient for recovery |
| DLQ messages | 30 days | Investigation window |

### Archival

- Completed sync records archived to cold storage after retention period
- Archived data queryable but not in hot path
- Queue archives retained for bounded period aligned with recovery requirements

### Deletion Workflows

- Core records follow lifecycle policies
- Support deletion workflows where required (e.g., GDPR requests)
- PII handling follows explicit classification and retention rules
