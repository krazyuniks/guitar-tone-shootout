---
github_issue: 111
title: "Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer (5A/5B/5D)"
state: OPEN
labels: ["epic"]
fetched: 2026-02-15T02:49:58Z
---

## Epic: Phase 5 Pipeline

Complete the T3K-to-GTS data pipeline: fix job system runtime wiring (5A), finish T3K source adapter with interleaved sync (5B), and build the pgmq consumer that upserts to gts_core (5D).

### Context

Epic E94 delivered significant partial implementations of Phases 5A and 5B. However, critical runtime wiring gaps remain — the worker only runs TaskIQ (not admin API or pgmq consumer), the webapp→worker enqueue path is broken, and the pgmq consumer doesn't exist yet.

This epic gets the data pipeline working end-to-end: T3K API → staging DB → pgmq queue → consumer → gts_core.

### Pre-requisites

Phases 1–4 (core) ✅ complete.

**Can run in parallel with:** Epic #95 (Phase 4 Completion)
**Blocks:** Phase 5 Features epic (5C/5E/5F/5V)

### Scope

#### Phase 5A — Job System (Partial → Complete)

**Exists:** Worker container, admin API (health, jobs CRUD), scheduler tasks (stale monitor, retries, heartbeat), distributed lock
**Gaps:**
- Update worker Docker Compose command to run all 3 services: admin API (port 8001) + TaskIQ worker + pgmq consumer
- `POST /api/admin/enqueue` endpoint for webapp→worker job dispatch
- Verify scheduler task registration with broker at runtime
- T3K admin endpoints on worker: `GET /api/admin/t3k/sync/status`, `POST /api/admin/t3k/sync`, `GET /api/admin/t3k/sync/stats`, `GET /api/admin/t3k/sync/lag`, `GET /api/admin/t3k/errors/summary`, `GET /api/admin/t3k/auth/status`
- `GET /api/admin/jobs/dead-lettered` — list dead-lettered jobs
- `GET /api/admin/jobs/pending-retries/count` — count pending retry jobs
- Lock management: `POST /api/admin/t3k/sync/unlock`, `POST /api/admin/scheduler/unlock`
- `ensure_source_sync_running` scheduler task (*/5 min — auto-start sync if not running)
- `SOURCE_SYNC` job handler (receives trigger, starts sync service)
- gts-admin Python CLI registered as `just admin` (commands: t3k-status, t3k-sync, jobs, job-health, unlock-sync, unlock-scheduler)

#### Phase 5B — T3K Source Adapter (Partial → Complete)

**Exists:** Domain models (T3KPack, T3KModel, T3KCreator), API client with rate limiter + circuit breaker, OAuth manager (Fernet), sync service with separate backfill/newest strategies, GearSyncRecord pgmq publisher, checkpoint persistence
**Gaps:**
- Migration for missing staging tables: `t3k_tags`, `t3k_makes`, `t3k_pack_images`, `t3k_pack_links`, `oauth_tokens` (in gts_t3k_source)
- Interleaved backfill+newest sync loop (`run_catalog_sync()`) — alternating backfill walk + newest check with skip-recently-synced and stale detection
- Model file download service — download NAM files to `source_downloads/t3k/{source_uuid}`, SHA-256 checksum validation
- T3K auth refresh scheduled task (every 12h via scheduler)

#### Phase 5D — pgmq Consumer (New)

**Exists:** Nothing — entirely new
**Deliverables:**
- Dual database session factory in worker (gts_core write pool + gts_t3k_source read pool)
- pgmq consumer polling loop: `pgmq.read_with_poll('gear_sync', vt=60, qty=10)` from gts_t3k_source
- Message validation against `GearSyncRecord` schema (from `libs/core/records/`)
- `GearMapperService` — idempotent upsert to gts_core using `(source_name, source_record_id, source_updated_at)` last-write-wins
- File migration: move files from `source_downloads/{source}/{source_uuid}` to `models/{core_uuid}.nam` within UoW transaction
- Dead letter queue handling: when `read_ct` exceeds max retries, move to `gear_sync_dlq`
- `pgmq.archive()` on success (preserves audit trail)
- Notification triggers for gear removal/invalidation (via Phase 4E NotificationService if available)

### Dependency Graph

```
Wave 1:  5A-wiring  5B-migrations  (parallel)
              │          │
Wave 2:  5A-endpoints  5B-sync-loop  5B-downloads  (parallel)
              │          │               │
Wave 3:  5A + 5B → 5D-consumer  (needs job system + source data)
              │
Wave 4:  5A → gts-admin CLI, SOURCE_SYNC handler
```

### Consumer Flow (5D)

```
1. pgmq.read_with_poll('gear_sync', vt=60, qty=10)  # from gts_t3k_source
2. Check read_ct > max_retries → DLQ if exceeded
3. Validate message against GearSyncRecord schema
4. Verify model file exists in source_downloads/
5. Begin UoW transaction (gts_core):
   a. Insert/update Gear + GearModel
   b. Move file to models/{core_uuid}.nam
   c. Queue notifications if gear removed/invalidated
   d. Commit
6. pgmq.archive('gear_sync', msg_id)  # in gts_t3k_source
```

### Verification

- `just check` passes
- `just test-regression` passes
- `just test-golden-path` passes
- Worker Docker Compose starts all 3 services (admin API + TaskIQ + pgmq consumer)
- `POST /api/admin/enqueue` dispatches jobs successfully
- T3K sync runs end-to-end (interleaved backfill + newest)
- Model files download with checksum validation
- pgmq consumer processes `gear_sync` messages
- Gear + GearModel appear in gts_core after sync
- Dead-lettered messages land in `gear_sync_dlq`
- `just admin t3k-status` returns formatted dashboard
- `just admin jobs` lists jobs from worker API

### Key Files

| File | Action |
|------|--------|
| `docker-compose.yml` | Update worker command to run admin API + TaskIQ + pgmq consumer |
| `apps/worker/src/worker/admin.py` | Extend — T3K endpoints, lock management, enqueue, dead-letter |
| `apps/worker/src/worker/db.py` | Add dual database session factory (gts_core + gts_t3k_source) |
| `apps/worker/src/worker/consumers/gear_sync.py` | Create — pgmq consumer loop |
| `apps/worker/src/worker/services/gear_mapper.py` | Create — GearSyncRecord → Gear upsert |
| `apps/worker/src/worker/jobs/source_sync.py` | Create — SOURCE_SYNC job handler |
| `sources/t3k/src/source_t3k/services/sync_service.py` | Refactor — interleaved backfill+newest loop |
| `sources/t3k/src/source_t3k/services/model_downloader.py` | Create — NAM file download + checksum |
| `apps/scheduler/src/scheduler/schedules/jobs.py` | Extend — ensure_source_sync_running |
| `apps/scheduler/src/scheduler/schedules/auth.py` | Create — T3K auth refresh (every 12h) |
| `scripts/gts-admin` | Create — Python CLI calling worker admin API |

### References

- [IMPLEMENTATION.md](../wiki/IMPLEMENTATION.md) — Phases 5A, 5B, 5D
- [GTS-Technical-Architecture](../wiki/GTS-Technical-Architecture.md) — Data ingestion pipeline, pgmq consumer, job scheduling
