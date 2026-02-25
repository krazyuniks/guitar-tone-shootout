# Plan: Epic #120

## Goal

Consolidate from dual-database to single-database architecture with BC table prefixes (core_*, t3k_*, msg_*) and align pgmq queues to the canonical 6-queue topology

## Observable Truths

1. After running migrations, all 24 core domain tables have the core_ prefix in the database (e.g. users → core_users, gear → core_gear)
2. After running migrations, T3K staging tables use semantic names: t3k_tones_staging, t3k_models_staging, t3k_users_staging (t3k_sync_checkpoints unchanged)
3. After database reset, exactly 6 pgmq queues exist: audio_commands, audio_events, video_commands, video_events, source_events, dead_letter — no legacy queues remain
4. After running migrations, the msg_consumer_offsets table exists with columns consumer_id TEXT, queue_name TEXT, last_processed_id BIGINT, updated_at TIMESTAMPTZ, and composite primary key (consumer_id, queue_name)
5. All containers (webapp, t3k-sync, audio-worker, video-worker, db, nginx) start without errors after database reset and migration
6. Running just check passes cleanly — lint, type checking, and import-linter all report zero errors
7. T3K_DATABASE_URL environment variable is completely removed from docker-compose.yml, WorkerSettings, worker/db.py, and .env.example
8. No references to gts_t3k_source remain anywhere in the codebase outside of historical Alembic migration scripts
9. Consumer and publisher code uses canonical queue names: audio-worker reads audio_commands, video-worker reads video_commands, t3k-sync publishes to source_events, all failed messages route to shared dead_letter queue

## User Journeys

### Journey J1: Developer performing database reset after pulling the consolidation branch

Developer pulls the branch, runs just db-reset to recreate the database from scratch, then runs just migrate to apply all migrations. They connect to psql and run \dt to verify all tables — they see 24 core_* tables, t3k_tones_staging / t3k_models_staging / t3k_users_staging, t3k_sync_checkpoints, and msg_consumer_offsets. They run SELECT queue_name FROM pgmq.list_queues() and see exactly 6 queues. They start all containers with just up-d and verify all are healthy with docker compose ps.

**Truths covered:** 1, 2, 3, 4, 5
**Entry point:** terminal
**Critical transitions:**
- terminal -> database reset complete (just db-reset && just migrate)
- database reset complete -> table verification (just psql -c '\dt core_*')
- table verification -> queue verification (just psql -c 'SELECT queue_name FROM pgmq.list_queues()')
- queue verification -> containers healthy (just up-d && docker compose ps)

### Journey J2: Developer verifying message flow through canonical queue topology

Developer starts all containers and tails logs for the t3k-sync, audio-worker, and video-worker containers. They verify t3k-sync publishes to source_events (not gear_sync), audio-worker consumes from audio_commands (not process_audio), and video-worker consumes from video_commands (not render_video). All containers remain healthy and connected to their canonical queues.

**Truths covered:** 3, 5, 9
**Entry point:** terminal
**Critical transitions:**
- terminal -> containers running (just up-d)
- containers running -> log inspection (docker compose logs t3k-sync audio-worker video-worker)
- log inspection -> queue name verification (Confirm logs reference audio_commands, video_commands, source_events)

### Journey J3: Developer verifying codebase hygiene after consolidation

Developer runs just check and sees all quality gates pass — zero lint errors, zero type errors, zero import-linter violations. They grep the codebase for gts_t3k_source and find no references outside migration scripts. They grep for T3K_DATABASE_URL and find zero references. They grep for old queue names (process_audio, render_video, gear_sync as queue names) in consumer/publisher code and find only the message type discriminators, not queue name assignments. The codebase is clean.

**Truths covered:** 6, 7, 8, 9
**Entry point:** terminal
**Critical transitions:**
- terminal -> quality gates pass (just check)
- quality gates pass -> legacy reference check (grep -rn gts_t3k_source --include='*.py' (excluding migrations/))
- legacy reference check -> clean codebase confirmed (grep -rn T3K_DATABASE_URL (zero results))

## Stories

### Story: BC table prefix Alembic migration and ORM model updates (`01-table-prefix-migration`)

**Purpose:** Create an Alembic migration that renames all 24 core tables to core_* prefix and 3 T3K staging tables to semantic names, then update all ORM model __tablename__ attributes and ForeignKey string references to match

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []

**Scope:**
- Create: `infrastructure/migrations/versions/0016_bc_table_prefixes.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user_identity.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user_gear.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/job.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout_comment.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear_model.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear_source.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/block_type.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/tag.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/notification.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/preset.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/models.py`

**Wiki Sections:** Database, Domain Model, Database Architecture

**Implementation Notes:**
- Alembic migration 0016: revision='0016', down_revision='0015'. Use op.rename_table() for all renames. Include both upgrade (old→new) and downgrade (new→old).
- Core table renames (24): users→core_users, oauth_providers→core_oauth_providers, user_identities→core_user_identities, user_gear→core_user_gear, jobs→core_jobs, audit_logs→core_audit_logs, shootouts→core_shootouts, di_tracks→core_di_tracks, shootout_chains→core_shootout_chains, audio_segments→core_audio_segments, shootout_comments→core_shootout_comments, gear→core_gear, gear_makes→core_gear_makes, tags→core_tags, gear_tags→core_gear_tags, gear_models→core_gear_models, gear_sources→core_gear_sources, signal_chains→core_signal_chains, signal_chain_blocks→core_signal_chain_blocks, signal_chain_groups→core_signal_chain_groups, block_types→core_block_types, user_tags→core_user_tags, presets→core_presets, user_notifications→core_user_notifications.
- T3K table renames (3): t3k_creators→t3k_users_staging, t3k_packs→t3k_tones_staging, t3k_models→t3k_models_staging. t3k_sync_checkpoints stays unchanged.
- PostgreSQL auto-updates FK constraint targets when tables are renamed — auxiliary T3K tables (t3k_tags, t3k_makes, t3k_pack_images, t3k_pack_links) do NOT need migration changes.
- Update all 14 core ORM model __tablename__ attributes to use core_ prefix.
- Update the gear_tags_table Table() definition in gear.py: table name 'gear_tags'→'core_gear_tags', ForeignKey('gear.id')→'core_gear.id', ForeignKey('tags.id')→'core_tags.id'.
- Update all ~28 ForeignKey string references across core model files to use core_ prefixed table names (e.g. ForeignKey('users.id')→ForeignKey('core_users.id')).
- Update 3 T3K ORM models in sources/t3k/src/source_t3k/adapters/outbound/models.py: T3KUserStaging.__tablename__='t3k_users_staging', T3KToneStaging.__tablename__='t3k_tones_staging', T3KModelStaging.__tablename__='t3k_models_staging'.
- Do NOT change any message_type literals (gear_sync, gear_synced, process_audio, render_video) — these are protocol discriminators, not table or queue names.
- Do NOT change JobType enum values (GEAR_SYNC='gear_sync') — these are domain concepts.

**Truths Addressed:** 1, 2

---

### Validation Checkpoint: After BC table prefix Alembic migration and ORM model updates

**Type:** quality
**Checks:**
- Regression tests pass with updated ORM tablename and ForeignKey values (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/regression/`]
- Type checking passes with no errors from updated ORM model attributes (evidence: command, exit_code, output_tail) [cmd: `just check-types`]

---

### Story: Canonical 6-queue topology and consumer/publisher updates (`02-queue-topology`)

**Purpose:** Rewrite init-core-db.sh to create exactly 6 canonical queues, create the msg_consumer_offsets Alembic migration, update all consumer and publisher queue name references, and delete dead init scripts

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []

**Scope:**
- Create: `infrastructure/migrations/versions/0017_msg_consumer_offsets.py`
- Modify: `infrastructure/docker/init-core-db.sh`
- Modify: `apps/audio_worker/src/audio_worker/consumer.py`
- Modify: `apps/video_worker/src/video_worker/consumer.py`
- Modify: `apps/t3k_sync/src/t3k_sync/consumer.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`
- Modify: `apps/t3k_sync/src/t3k_sync/source_sync.py`

**Wiki Sections:** Queue Topology, Container Topology, Message Catalogue, Messaging & Job Scheduling

**Implementation Notes:**
- Rewrite init-core-db.sh to create exactly 6 queues: audio_commands, audio_events, video_commands, video_events, source_events, dead_letter. Remove all 14 legacy queue creation lines. Keep pg_partman and pgmq extension creation. Keep GRANT statements.
- Delete infrastructure/docker/init-db.sql (dead file — creates gts_t3k_source but is not mounted in docker-compose).
- Delete infrastructure/docker/init-pgmq.sql (dead file — not mounted in docker-compose).
- Create Alembic migration 0017: revision='0017', down_revision='0016'. CREATE TABLE msg_consumer_offsets (consumer_id TEXT NOT NULL, queue_name TEXT NOT NULL, last_processed_id BIGINT NOT NULL, updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (consumer_id, queue_name)). Downgrade drops the table.
- Update audio_worker/consumer.py: queue_name='process_audio'→'audio_commands', dead_letter_queue='process_audio_dlq'→'dead_letter'.
- Update video_worker/consumer.py: queue_name='render_video'→'video_commands', dead_letter_queue='render_video_dlq'→'dead_letter'.
- Update t3k_sync/consumer.py: queue_name='gear_sync'→'source_events', dead_letter_queue='gear_sync_dlq'→'dead_letter'.
- Update source_t3k/publisher.py: default queue_name='gear_sync'→'source_events' in __init__ parameter.
- Update t3k_sync/source_sync.py: GearSyncPublisher instantiation queue_name='gear_sync'→'source_events'.
- Do NOT change message_type discriminators (process_audio, render_video, gear_sync) — these are protocol identifiers, not queue names.
- Do NOT implement event publishing or offset-based consumption logic — that is deferred to Epic #121. Only create the DDL.

**Truths Addressed:** 3, 4, 9

---

### Validation Checkpoint: After Canonical 6-queue topology and consumer/publisher updates

**Type:** quality
**Checks:**
- init-core-db.sh creates the 6 canonical queues (audio_commands present as representative check) (evidence: command, exit_code, output_tail) [cmd: `grep -q 'audio_commands' infrastructure/docker/init-core-db.sh && grep -q 'source_events' infrastructure/docker/init-core-db.sh && grep -q 'dead_letter' infrastructure/docker/init-core-db.sh`]
- Type checking passes with updated consumer/publisher queue name strings (evidence: command, exit_code, output_tail) [cmd: `just check-types`]

---

### Story: Remove dual-database infrastructure and legacy compatibility shim (`03-dual-database-elimination`)

**Purpose:** Eliminate all traces of the dual-database architecture: remove T3K_DATABASE_URL from config and docker-compose, remove backward-compatible session aliases, delete the legacy GearSyncConsumer shim, delete the dead T3K alembic.ini, delete one-time migration scripts, and update remaining gts_t3k_source references in tooling code

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []

**Scope:**
- Modify: `docker-compose.yml`
- Modify: `apps/worker/src/worker/config.py`
- Modify: `apps/worker/src/worker/db.py`
- Modify: `.env.example`
- Modify: `scripts/sync_from_archive.py`
- Modify: `scripts/migrate_t3k_data.py`
- Modify: `workflow/context_assembler.py`
- Modify: `worktree/backup.py`

**Wiki Sections:** Database, Infrastructure Management & Workflow

**Implementation Notes:**
- Remove T3K_DATABASE_URL from 4 services in docker-compose.yml: worker (~line 147), t3k-sync (~line 196), audio-worker (~line 243), video-worker (~line 296).
- Remove t3k_database_url field from WorkerSettings in apps/worker/src/worker/config.py. Update the docstring to reflect single-database architecture.
- Remove get_t3k_session() and get_t3k_session_no_tx() from apps/worker/src/worker/db.py. These are backward-compat aliases that just call get_core_session(). Keep get_core_session() and get_core_session_no_tx().
- Update .env.example: remove the 'ARCHITECTURE: Dual database with worker as bridge' comment block, remove T3K_DATABASE_URL references, update DB_PASSWORD comment to remove 'shared between gts_core and gts_t3k_source'.
- Delete apps/worker/src/worker/consumers/gear_sync.py (legacy compatibility shim). The consumers/__init__.py is just a docstring — no update needed.
- Delete sources/t3k/alembic.ini (dead config file — T3K migration chain was never initialised).
- Delete scripts/sync_from_archive.py — one-time archive sync script whose work is complete. All 4 hardcoded gts_t3k_source psql calls would break under single-database architecture.
- Delete scripts/migrate_t3k_data.py — one-time data migration script whose work is complete. Contains hardcoded gts_t3k_source fallback that is no longer valid.
- Update workflow/context_assembler.py: rename the 'dual_database' context key to 'database_architecture' (or similar), change its description from 'gts_core vs gts_t3k_source boundaries' to 'Single database with BC table prefixes (core_*, t3k_*, msg_*)', and update the questions field accordingly.
- Update worktree/backup.py: change the docstring example from "e.g. ['gts_core', 'gts_t3k_source']" to "e.g. ['gts_core']" to reflect single-database architecture.

**Truths Addressed:** 7, 8

---

### Story: Update and clean up test suite for consolidated architecture (`04-test-alignment`)

**Purpose:** Delete test files that validate removed functionality, update remaining tests to use new table names, queue names, and single-database config, then verify all quality gates and tests pass

**Agent:**
- model: codex
- skills: [gts-testing]
- tools: []

**Scope:**
- Modify: `tests/unit/worker/conftest.py`
- Modify: `tests/unit/worker/test_worker_config.py`
- Modify: `tests/integration/worker/test_single_database.py`
- Modify: `tests/integration/worker/test_worker_db.py`
- Modify: `tests/integration/scheduler/test_sync_dispatch.py`
- Modify: `tests/integration/worker/test_pgmq_consumer_wiring.py`
- Modify: `tests/unit/t3k/test_publisher.py`
- Modify: `tests/integration/t3k/test_publisher.py`
- Modify: `tests/unit/core/test_messaging.py`

**Wiki Sections:** Testing Strategy, Database Architecture

**Implementation Notes:**
- DELETE tests/unit/worker/test_gear_sync_consumer.py — tests the legacy GearSyncConsumer shim that was removed in story 03.
- DELETE tests/integration/worker/test_dual_database_sessions.py — tests dual-database session support that no longer exists.
- DELETE tests/integration/t3k/test_t3k_migrations.py — tests T3K alembic.ini that was deleted in story 03.
- Update tests/unit/worker/conftest.py: remove T3K_DATABASE_URL from the list of env vars to clean in isolate_worker_env fixture.
- Update tests/unit/worker/test_worker_config.py: remove t3k_database_url from all WorkerSettings instantiations. Remove test_settings_has_t3k_database_url_field and test_t3k_database_url_field_is_required test methods. Update remaining tests that construct WorkerSettings to omit t3k_database_url.
- Update tests/integration/worker/test_single_database.py: replace get_t3k_session with get_core_session in imports and assertions.
- Update tests/integration/worker/test_worker_db.py: remove t3k_database_url from any WorkerSettings constructions.
- Update tests/integration/scheduler/test_sync_dispatch.py: remove monkeypatch.setenv('T3K_DATABASE_URL', ...) and register_engine calls for T3K URL.
- Update tests/integration/worker/test_pgmq_consumer_wiring.py: change queue name assertions from 'gear_sync'→'source_events' and 'gear_sync_dlq'→'dead_letter'. Update get_t3k_session references to get_core_session.
- Update tests/unit/t3k/test_publisher.py: change queue_name='gear_sync'→'source_events' in GearSyncPublisher instantiations.
- Update tests/integration/t3k/test_publisher.py: change queue_name='gear_sync'→'source_events' in GearSyncPublisher instantiations.
- Run just check to verify lint + types + imports all pass. Run just tdd tests/unit/ and just tdd tests/integration/ to verify all tests pass. Fix any remaining failures.

**Truths Addressed:** 5, 6

---

### Validation Checkpoint: After Update and clean up test suite for consolidated architecture

**Type:** quality
**Checks:**
- Full quality gates pass: lint, types, and import-linter (evidence: command, exit_code, output_tail) [cmd: `just check`]
- All unit tests pass with updated config and queue names (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/unit/`]
- All integration tests pass with single-database architecture (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. After running migrations, all 24 core domain tables have the core_ prefix in the database (e.g. users → core_users, gear → core_gear) | `infrastructure/migrations/versions/0016_bc_table_prefixes.py`, `apps/webapp/src/webapp/adapters/persistence/models/user.py`, `apps/webapp/src/webapp/adapters/persistence/models/user_identity.py` (+13 more) | BC table prefix Alembic migration and ORM model updates |
| 2. After running migrations, T3K staging tables use semantic names: t3k_tones_staging, t3k_models_staging, t3k_users_staging (t3k_sync_checkpoints unchanged) | `infrastructure/migrations/versions/0016_bc_table_prefixes.py`, `apps/webapp/src/webapp/adapters/persistence/models/user.py`, `apps/webapp/src/webapp/adapters/persistence/models/user_identity.py` (+13 more) | BC table prefix Alembic migration and ORM model updates |
| 3. After database reset, exactly 6 pgmq queues exist: audio_commands, audio_events, video_commands, video_events, source_events, dead_letter — no legacy queues remain | `infrastructure/migrations/versions/0017_msg_consumer_offsets.py`, `infrastructure/docker/init-core-db.sh`, `apps/audio_worker/src/audio_worker/consumer.py` (+4 more) | Canonical 6-queue topology and consumer/publisher updates |
| 4. After running migrations, the msg_consumer_offsets table exists with columns consumer_id TEXT, queue_name TEXT, last_processed_id BIGINT, updated_at TIMESTAMPTZ, and composite primary key (consumer_id, queue_name) | `infrastructure/migrations/versions/0017_msg_consumer_offsets.py`, `infrastructure/docker/init-core-db.sh`, `apps/audio_worker/src/audio_worker/consumer.py` (+4 more) | Canonical 6-queue topology and consumer/publisher updates |
| 5. All containers (webapp, t3k-sync, audio-worker, video-worker, db, nginx) start without errors after database reset and migration | `tests/unit/worker/conftest.py`, `tests/unit/worker/test_worker_config.py`, `tests/integration/worker/test_single_database.py` (+6 more) | Update and clean up test suite for consolidated architecture |
| 6. Running just check passes cleanly — lint, type checking, and import-linter all report zero errors | `tests/unit/worker/conftest.py`, `tests/unit/worker/test_worker_config.py`, `tests/integration/worker/test_single_database.py` (+6 more) | Update and clean up test suite for consolidated architecture |
| 7. T3K_DATABASE_URL environment variable is completely removed from docker-compose.yml, WorkerSettings, worker/db.py, and .env.example | `docker-compose.yml`, `apps/worker/src/worker/config.py`, `apps/worker/src/worker/db.py` (+5 more) | Remove dual-database infrastructure and legacy compatibility shim |
| 8. No references to gts_t3k_source remain anywhere in the codebase outside of historical Alembic migration scripts | `docker-compose.yml`, `apps/worker/src/worker/config.py`, `apps/worker/src/worker/db.py` (+5 more) | Remove dual-database infrastructure and legacy compatibility shim |
| 9. Consumer and publisher code uses canonical queue names: audio-worker reads audio_commands, video-worker reads video_commands, t3k-sync publishes to source_events, all failed messages route to shared dead_letter queue | `infrastructure/migrations/versions/0017_msg_consumer_offsets.py`, `infrastructure/docker/init-core-db.sh`, `apps/audio_worker/src/audio_worker/consumer.py` (+4 more) | Canonical 6-queue topology and consumer/publisher updates |
