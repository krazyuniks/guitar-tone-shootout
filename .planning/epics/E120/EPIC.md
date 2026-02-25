---
github_issue: 120
title: "Database consolidation: single database, BC table prefixes, canonical queue topology"
state: OPEN
labels: ["epic"]
fetched: 2026-02-25T11:37:37Z
---

## Summary

Consolidate from dual-database (`gts_core` + `gts_t3k_source`) to single-database
(`gts_core`) architecture. Add BC table prefixes (`core_*`, `t3k_*`). Align pgmq
queues with the 6-queue canonical topology. Create `msg_consumer_offsets` table for
event consumer offset tracking.

Reference: [Jobs-Architecture-and-Operations wiki](../wiki/Jobs-Architecture-and-Operations.md)

## Observable Outcomes

### Database consolidation
- [ ] `gts_t3k_source` database eliminated — all tables live in `gts_core`
- [ ] `init-db.sql` no longer creates `gts_t3k_source`
- [ ] `init-pgmq.sql` deleted — queue creation consolidated into `init-core-db.sh`
- [ ] `T3K_DATABASE_URL` env var removed from all config, docker-compose, and app code
- [ ] Dual-database session infrastructure removed (worker `get_t3k_session`, `WorkerSettings.t3k_database_url`)
- [ ] T3K Alembic migrations run against `gts_core` (single migration chain)
- [ ] Data migration script moves existing t3k data from `gts_t3k_source` → `gts_core` (idempotent)

### BC table prefixes
- [ ] Core tables renamed with `core_` prefix (Alembic migration: `ALTER TABLE RENAME`)
  - e.g. `users` → `core_users`, `gear` → `core_gear`, `jobs` → `core_jobs`
  - Full list: 24 tables per wiki spec
- [ ] Core ORM models updated: `__tablename__` uses `core_` prefix
- [ ] T3K staging tables renamed to wiki spec (Alembic migration):
  - `t3k_packs` → `t3k_tones_staging`
  - `t3k_models` → `t3k_models_staging`
  - `t3k_creators` → `t3k_users_staging`
  - `t3k_sync_checkpoints` unchanged
- [ ] T3K ORM models updated with new table names

### Queue topology
- [ ] `init-core-db.sh` creates exactly 6 queues: `audio_commands`, `audio_events`,
  `video_commands`, `video_events`, `source_events`, `dead_letter`
- [ ] Old queues removed: `gear_sync`, `gear_sync_dlq`, `gear_pack_sync`,
  `gear_model_sync`, `preset_sync`, `sync_dead_letter`, `audio_processing`,
  `video_composition`, `notifications`, `jobs_dead_letter`, `process_audio`,
  `process_audio_dlq`, `render_video`, `render_video_dlq`
- [ ] `msg_consumer_offsets` table created via Alembic migration with schema:
  `(consumer_id TEXT, queue_name TEXT, last_processed_id BIGINT, updated_at TIMESTAMPTZ,
  PRIMARY KEY (consumer_id, queue_name))`

### BC consumer/publisher updates
- [ ] audio-worker listens on `audio_commands` (was `process_audio`)
- [ ] video-worker listens on `video_commands` (was `render_video`)
- [ ] t3k-sync publishes to `source_events` (was `gear_sync`)
- [ ] DLQ references updated to shared `dead_letter` (was per-queue DLQs)
- [ ] Command schemas in `infra/messaging/` reference correct queue names

### Verification
- [ ] All containers start without errors
- [ ] T3K sync container syncs gear data through `source_events` queue
- [ ] `just check` passes
- [ ] No references to `gts_t3k_source` remain in codebase (except migration scripts)

## Decisions

- Single database is a breaking change — requires `just db-reset` on dev databases
- `msg_consumer_offsets` and table renames created via Alembic for proper migration tracking
- DLQ strategy: single shared `dead_letter` queue (not per-queue DLQs)
- T3K staging tables are owned exclusively by `source_t3k` BC — core ingests via pgmq events only

## Regression Boundaries

- All containers start without errors
- T3K sync container syncs gear data through `source_events` queue
- No changes to authentication, webapp routes, or domain logic
- `just check` passes
