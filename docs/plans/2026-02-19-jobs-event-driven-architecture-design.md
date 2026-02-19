# Jobs & Event-Driven Architecture Design

> Status: **DESIGN COMPLETE** — all architectural decisions agreed. Ready for
> implementation planning.
>
> This document synthesises and supersedes:
> - `2026-02-19-bounded-context-architecture.md`
> - `2026-02-19-core-job-dispatch-decoupling.md`
> - `2026-02-19-jobs-wiki-consolidation-plan.md`
>
> Those three files will be deleted once 100% of their detail is accounted for here.

---

## 1. Problem Statement

The current system has three logical bounded contexts (Core, Source: T3K,
Execution) but boundaries are not enforced at the infrastructure level:

- The worker service straddles every context, imports webapp ORM models directly.
- The `jobs` table is a shared monolith (SOURCE_SYNC lives in `gts_core`).
- Webapp HTTP-calls worker admin API for job dispatch (user request depends on
  worker availability).
- Scheduler HTTP-calls worker for sync triggering and token refresh.
- The only correct pattern is `gear_sync` (pgmq transactional publish + consumer),
  but even that publishes after commit rather than within the transaction.
- Two separate databases (`gts_core`, `gts_t3k_source`) prevent cross-BC
  transactional messaging.
- Job orchestration (shootout → audio → master → video) is hidden in function
  call chains and direct `.kiq()` dispatches.
- Progress notification infrastructure exists (Redis pub/sub + WebSocket) but
  handlers don't use it.
- TaskIQ + Redis add unnecessary dependencies when pgmq can handle both
  messaging and task dispatch.
- The scheduler exists solely to HTTP-trigger jobs that should be self-driven.

---

## 2. Design Decisions (Agreed)

### 2.1 Single Database

Merge `gts_t3k_source` into the main database. All BCs share one PostgreSQL
instance with one database. BC separation is enforced via:

- **Code**: import-linter contracts (already enforced).
- **Table naming**: strict BC prefix on every table (`core_jobs`, `core_gear`,
  `t3k_tone_staging`, etc.).
- **ORM isolation**: each BC's SQLAlchemy models/datamappers MUST only reference
  their own BC's tables. A BC must NEVER load, query, or inspect another BC's
  tables.

This eliminates cross-database transaction problems. All commands, events, and
domain state changes can be written in a single transaction.

**Critical rule — agents and developers:**

> A BC can only load its own tables. Its domain model, SQLAlchemy ORM, and
> datamapper must only know about its own domain model. Agents must NEVER
> `show tables`, `\dt`, or inspect the full database schema when working on a
> BC problem. Only inspect the BC's own models and migrations.

### 2.2 Event-Driven Architecture (Commands + Events)

Two message types, same transactional outbox pattern:

| Type | Semantics | Delivery | Example |
|------|-----------|----------|---------|
| **Command** | Directed instruction to a specific BC | Point-to-point (pgmq queue) | Video BC → Audio BC: "produce master track" |
| **Event** | Notification of state change, consumer-agnostic | Multi-consumer (pgmq + offsets) | Audio BC: "chain audio processing complete" |

### 2.3 Transactional Outbox Rule

> All pgmq publishes MUST happen within the same database transaction as the
> domain state change. The `pgmq.send()` call and the INSERT/UPDATE that
> motivates it share one `commit()`. No publish-after-commit. No two-phase
> patterns. No exceptions.

This applies to ALL producers — commands, events, every BC.

### 2.4 Topic Types Per BC

Each bounded context has topics appropriate to its role:

| BC | Command topic (input) | Event topic (output) |
|----|----------------------|---------------------|
| **Audio** | `audio_commands` | `audio_events` |
| **Video** | `video_commands` | `video_events` |
| **Source: T3K** | _(none — self-driven)_ | `source_events` |

Source BCs have no command topic. The T3K sync is a continuously running loop
that polls the T3K API. It is not triggered by commands — it runs as a daemon
and publishes events when it finds new data.

All queues live in the single shared database as pgmq queues.

### 2.5 Thick Events

All messages (commands and events) carry rich metadata so consumers have
everything they need without querying back. No thin `{job_id}` messages.

Producers publish thick events to their topic. Any consumer that cares reads
the topic and does what it wants with the data. Producers don't know or care
who consumes their events.

**Command example** (`compose_shootout` on `video_commands`):

```json
{
  "type": "compose_shootout",
  "version": 1,
  "job_id": "uuid",
  "shootout_id": "uuid",
  "user_id": "uuid",
  "di_track_path": "audio/di_tracks/uuid.flac",
  "chains": [
    {"id": "uuid", "position": 1, "signal_chain_id": "uuid", "gear_blocks": [...]},
    {"id": "uuid", "position": 2, "signal_chain_id": "uuid", "gear_blocks": [...]}
  ]
}
```

**Event example** (`chain_audio_complete` on `audio_events`):

```json
{
  "type": "chain_audio_complete",
  "version": 1,
  "shootout_id": "uuid",
  "chain_id": "uuid",
  "segment_path": "audio/uuid/segments/01_uuid.flac",
  "duration_seconds": 45.2,
  "integrated_lufs": -14.0,
  "peak_dbfs": -1.2,
  "completed_at": "2026-02-19T12:00:00Z"
}
```

### 2.6 Event-Driven Choreography (No Central Orchestrator)

Each handler creates the next step on completion. No central orchestrator.
Each BC is in charge of its own work and sub-jobs.

**Shootout flow (user wants a video):**

```
Webapp
  → INSERT core_jobs row (type=VIDEO_COMPOSE)
  → pgmq.send('video_commands', {compose_shootout, ...thick metadata...})
  → commit (one transaction)

Video BC consumer reads video_commands
  → Knows it needs N audio tracks first
  → For each chain: pgmq.send('audio_commands', {process_chain_audio, ...})
  → commit

Audio BC consumer reads audio_commands
  → Processes chain audio through DSP pipeline
  → pgmq.send('audio_events', {chain_audio_complete, ...results...})
  → commit

Video BC consumer reads audio_events
  → "Are all chains for my shootout done?" → YES
  → pgmq.send('audio_commands', {produce_master_track, ...chain results...})
  → commit

Audio BC consumer reads audio_commands
  → Produces master track
  → pgmq.send('audio_events', {master_track_complete, ...results...})
  → commit

Video BC consumer reads audio_events
  → Master track ready. Renders video.
  → pgmq.send('video_events', {video_compose_complete, ...})
  → Updates core_jobs status to COMPLETED
  → commit

Webapp (or any consumer) reads video_events
  → Updates UI, notifies user
```

**Standalone audio flow (user wants audio for listening):**

```
Webapp
  → INSERT core_jobs row (type=AUDIO_PROCESSING)
  → pgmq.send('audio_commands', {process_audio_file, ...thick metadata...})
  → commit

Audio BC consumer reads audio_commands
  → Processes audio
  → pgmq.send('audio_events', {audio_file_complete, ...results...})
  → Updates core_jobs status to COMPLETED
  → commit
```

**T3K sync flow (continuous):**

```
T3K sync container starts
  → Enters eternal loop polling T3K API
  → Finds new gear data
  → pgmq.send('source_events', {gear_synced, ...thick payload...})
  → commit
  → Continue polling

Any consumer (e.g. webapp/core) reads source_events
  → Upserts into core_gear, core_gear_models, etc.
  → Updates offset
```

### 2.7 Queue Implementation

**pgmq is just SQL functions and tables inside PostgreSQL.** `pgmq.send()`
inserts a row. `pgmq.read()` selects a row with a visibility timeout.
`pgmq.archive()` moves it to an archive table. No separate process, no daemon.

**Consumer loops are our code.** Each BC container runs a `while True` loop
that calls `pgmq.read()`, processes the message, and calls `pgmq.archive()`.
We own these loops entirely.

**Commands (point-to-point):** standard pgmq — `pgmq.read()` → process →
`pgmq.archive()`. One consumer drains the queue. Visibility timeout for retry.
If the consumer crashes before archiving, the message reappears after timeout.

**Events (multi-consumer):** pgmq as append log with consumer offsets:

1. Producer writes via `pgmq.send()` — transactional with domain state.
2. Each consumer maintains its own offset (last processed `msg_id`) in a shared
   `msg_consumer_offsets` table.
3. Consumer polls using its offset from the pgmq queue.
4. After processing: updates offset.
5. Cleanup: periodically archive messages below the minimum offset across all
   registered consumers.

**Retries:** pgmq visibility timeout handles retries automatically. If a
consumer reads a message but crashes before archiving, the message becomes
visible again after the timeout period. After N failed attempts, move to DLQ.

**DLQ:** One shared dead-letter queue with routing metadata (source queue,
failure reason, attempt count).

**Event consumer registration:** Static configuration with schema validation
and proper error handling.

### 2.8 Database Table Layers

| Layer | Tables | Owned by |
|-------|--------|----------|
| BC domain | `core_jobs`, `core_gear`, `core_shootouts`, `t3k_tone_staging`, ... | Specific BC code (import-linter enforced) |
| pgmq queues | `pgmq.q_audio_commands`, `pgmq.q_video_events`, ... | Shared messaging infrastructure |
| Messaging state | `msg_consumer_offsets` | Shared messaging infrastructure |

### 2.9 One Container Per BC

Each bounded context runs as its own Docker container with its own process.
This is the strongest enforcement of BC isolation — not just code boundaries,
but process boundaries. Each container only has its own BC's code in the
import path.

| Container | BC | Role |
|-----------|-----|------|
| `webapp` | Core | FastAPI server, writes commands to pgmq, consumes events for UI updates |
| `t3k-sync` | Source: T3K | Eternal loop polling T3K API, publishes `source_events` |
| `audio-worker` | Audio | Polls `audio_commands`, publishes `audio_events` |
| `video-worker` | Video | Polls `video_commands` + reads `audio_events`, publishes `video_events` |
| `postgres` | — | Database (pgmq lives here) |
| `nginx` | — | Reverse proxy |

**Removed from current architecture:**

| Removed | Reason |
|---------|--------|
| `scheduler` | No remaining purpose. T3K sync is self-driven. On-demand jobs are triggered by user actions via pgmq commands. |
| `redis` | Was only needed as TaskIQ broker. pgmq replaces TaskIQ for task dispatch. WebSocket notifications are a future webapp concern. |
| `worker` (monolithic) | Replaced by per-BC containers (`audio-worker`, `video-worker`, `t3k-sync`). |
| TaskIQ dependency | pgmq consumer loops replace TaskIQ's poll-and-execute pattern. Same concept, one fewer dependency, transactional publish for free. |

### 2.10 Token Refresh Ownership

T3K token refresh is handled by the T3K sync container as part of its startup
lifecycle. `T3KSyncService` already calls `token_manager.ensure_valid_token()`.
Add proactive refresh if token expires within 10 minutes.

### 2.11 Import Decoupling

Each BC container only imports its own BC's code. Shared domain models (e.g.
base entities, value objects) live in `libs/core`. BC-specific models live in
their BC's library. This happens naturally with separate containers — no
special decoupling phase needed.

### 2.12 BC-Level CLAUDE.md Files

Each BC has its own `CLAUDE.md` file pointing to `AGENTS.md` for shared rules,
plus BC-specific rules, table ownership declarations, and implementation
guidelines.

### 2.13 Message Schema Validation

Pydantic models for all commands and events. Each BC defines its own message
schemas in its library (`libs/core/messages.py`, `libs/audio/messages.py`,
`libs/video/messages.py`). Follows existing Pydantic-everywhere pattern.

### 2.14 core_jobs as User-Facing Status

`core_jobs` remains the single user-facing aggregate for job status and
progress. The webapp queries it for "what's my job doing?" Event consumers
update it as they progress through the workflow. BCs treat it as part of the
core domain — conceptually a separate database. No abstraction leakage.

### 2.15 JobType Enum

`JobType` maps to command types. `JobType.VIDEO_COMPOSE` → `compose_shootout`
command, `JobType.SOURCE_SYNC` → removed (T3K sync is self-driven, not a job).
The enum stays as the user-facing label; command types are the internal
dispatch key.

---

## 3. Queue Topology (Target)

### Queues to create

| Queue | Type | Producer(s) | Consumer(s) |
|-------|------|-------------|-------------|
| `audio_commands` | Command | Webapp, Video BC | Audio BC consumer |
| `audio_events` | Event | Audio BC | Video BC, Webapp |
| `video_commands` | Command | Webapp | Video BC consumer |
| `video_events` | Event | Video BC | Webapp |
| `source_events` | Event | T3K sync | Webapp (core domain), monitoring |
| `dead_letter` | DLQ | Any consumer (on failure) | Monitoring/alerting |

### Queues to remove

- `audio_processing` (unused, never wired)
- `video_composition` (unused, never wired)
- `notifications` (unused, never wired)
- `jobs_dead_letter` (unused, never wired)
- `gear_sync` (replaced by `source_events`)
- `gear_pack_sync` (legacy)
- `gear_model_sync` (legacy)
- `sync_dead_letter` (replaced by shared `dead_letter` queue)
- `gear_sync_dlq` (replaced by shared `dead_letter` queue)
- `source_commands` (not needed — T3K sync is self-driven)

### New shared table

```sql
CREATE TABLE msg_consumer_offsets (
    consumer_id TEXT NOT NULL,
    queue_name TEXT NOT NULL,
    last_processed_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (consumer_id, queue_name)
);
```

---

## 4. Message Catalogue

### Commands

| Command type | Topic | Producer | Thick payload includes |
|-------------|-------|----------|----------------------|
| `compose_shootout` | `video_commands` | Webapp | job_id, shootout_id, user_id, di_track_path, chains with gear blocks |
| `process_audio_file` | `audio_commands` | Webapp | job_id, user_id, signal_chain_id, input_file_path, output_format |
| `process_chain_audio` | `audio_commands` | Video BC | shootout_id, chain_id, signal_chain_id, di_track_path, gear_paths |
| `produce_master_track` | `audio_commands` | Video BC | shootout_id, chain_results with segment paths and LUFS |

### Events

| Event type | Topic | Producer | Thick payload includes |
|-----------|-------|----------|----------------------|
| `chain_audio_complete` | `audio_events` | Audio BC | shootout_id, chain_id, segment_path, duration, LUFS, peak dBFS |
| `master_track_complete` | `audio_events` | Audio BC | shootout_id, master_path, duration, LUFS |
| `audio_file_complete` | `audio_events` | Audio BC | job_id, output_path, duration, LUFS |
| `video_compose_complete` | `video_events` | Video BC | shootout_id, job_id, video_path |
| `gear_synced` | `source_events` | T3K sync | GearSyncRecord format (already thick) |

---

## 5. Table Rename Map

All tables get strict BC prefix. Preliminary mapping (to be finalised during
implementation — requires full audit of both databases):

| Current name | New name | BC |
|-------------|----------|-----|
| `jobs` | `core_jobs` | Core |
| `gear` | `core_gear` | Core |
| `gear_models` | `core_gear_models` | Core |
| `gear_sources` | `core_gear_sources` | Core |
| `shootouts` | `core_shootouts` | Core |
| `shootout_chains` | `core_shootout_chains` | Core |
| `audio_segments` | `core_audio_segments` | Core |
| `signal_chains` | `core_signal_chains` | Core |
| `signal_chain_blocks` | `core_signal_chain_blocks` | Core |
| `di_tracks` | `core_di_tracks` | Core |
| `presets` | `core_presets` | Core |
| `tags` | `core_tags` | Core |
| `users` | `core_users` | Core |
| `user_gear` | `core_user_gear` | Core |
| `t3k_tone_staging` | `t3k_tone_staging` | Source: T3K |
| `t3k_model_staging` | `t3k_model_staging` | Source: T3K |
| `sync_checkpoints` | `t3k_sync_checkpoints` | Source: T3K |
| `t3k_oauth_tokens` | `t3k_oauth_tokens` | Source: T3K |

> Note: T3K tables already mostly have `t3k_` prefix. Core tables need renaming.
> Full audit of both databases required before implementation to ensure
> completeness.

---

## 6. Phase Breakdown

### Phase 0: Documentation baseline

- Write canonical wiki page `Jobs-Architecture-and-Operations.md`
- Refactor existing wiki pages (dedup, link to canonical page)
- Update AGENTS.md (outbox rule, BC communication patterns, table isolation rule)
- Update gts-architecture skill references
- Create/update BC-level CLAUDE.md files with table ownership declarations

### Phase 1: Single database migration

- Merge `gts_t3k_source` tables into main database (single Alembic migration)
- Rename all tables with BC prefixes (`core_*`, `t3k_*`)
- Update all ORM models, migrations, connection strings
- Simplify Docker compose (one DB init)
- Remove `T3K_DATABASE_URL` from all config
- Update import-linter contracts

### Phase 2: Command and event infrastructure

- Create pgmq queues: `audio_commands`, `audio_events`, `video_commands`,
  `video_events`, `source_events`
- Create shared `dead_letter` queue
- Create `msg_consumer_offsets` table
- Drop unused/legacy queues
- Build command consumer base (pgmq read/archive with visibility timeout retry)
- Build event consumer base (offset-based read pattern)
- Prototype offset-based event consumption with pgmq (implementation detail
  to be resolved during this phase)

### Phase 3: T3K sync container

- Extract T3K sync into its own container (`t3k-sync`)
- Eternal loop polling T3K API, no external trigger
- Publish thick events to `source_events` via transactional outbox
- Token refresh handled within sync container lifecycle
- Remove scheduler container and all scheduler code

### Phase 4: Audio BC container

- Extract audio processing into `audio-worker` container
- Polls `audio_commands`, processes work, publishes to `audio_events`
- Thick events with full results (paths, LUFS, duration, etc.)
- Transactional outbox for all publishes

### Phase 5: Video BC container

- Extract video processing into `video-worker` container
- Polls `video_commands` for new compose requests
- Reads `audio_events` (offset-based) to track chain completion
- Owns reconciliation logic ("are all chains done?")
- Publishes to `video_events` on completion

### Phase 6: Webapp decoupling

- Webapp writes commands to `audio_commands` or `video_commands` + core_jobs
  row (transactional outbox)
- Webapp consumes `source_events` to upsert core domain (gear mapping)
- Webapp consumes `video_events` for job completion updates
- Remove `enqueue_to_worker()` HTTP dispatch
- Remove direct `.kiq()` calls from all handlers

### Phase 7: Cleanup and removal

- Remove TaskIQ dependency entirely
- Remove Redis from infrastructure
- Remove monolithic worker container
- Remove scheduler container
- Clean up Docker compose (remove unused services, profiles, volumes)
- Update all documentation and configuration

---

## 7. Scope Includes

- Source code refactoring and implementation (Phases 1-7)
- Wiki documentation (canonical page + refactoring existing pages)
- AGENTS.md updates (rules, architecture table, patterns)
- BC-level CLAUDE.md files (table ownership, BC-specific rules)
- gts-architecture skill reference updates
- Pydantic message schemas per BC
- Docker compose topology changes
- Removal of TaskIQ, Redis, scheduler

---

## 8. Resolved Design Questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | pgmq offset-based event consumption detail | Defer to Phase 2 prototyping |
| 2 | DLQ strategy | One shared DLQ with routing metadata |
| 3 | Schema migration strategy | Single Alembic migration |
| 4 | Table rename completeness | Full audit required before Phase 1 |
| 5 | Message schema validation | Pydantic models per BC library |
| 6 | core_jobs role | User-facing status aggregate. BCs update it via events. No abstraction leakage. |
| 7 | TaskIQ's role | **Eliminated.** pgmq consumer loops replace TaskIQ entirely. Redis removed. |
| 8 | Progress notifications | Webapp concern only. Not part of this architecture. Will be triggered by events but implementation is webapp-owned. |
| 9 | Detailed thick event schemas | Deferred to implementation |
| 10 | Consumer registration | Static configuration with schema validation |
| 11 | JobType enum | Maps to command types. Enum stays as user-facing label. SOURCE_SYNC removed (T3K sync is self-driven). |
| 12 | Reconciliation pattern | Each BC owns its own sub-job tracking and reconciliation |

---

## 9. Remaining Work

- [ ] Full database audit (both databases) to complete table rename map
- [ ] Write canonical wiki page
- [ ] Create implementation plan (invoke writing-plans skill)
