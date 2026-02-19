# Jobs & Event-Driven Architecture Design

> Status: **IN PROGRESS** — brainstorming session paused. Architecture decisions
> agreed. Phase breakdown and implementation detail still needed.
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

### 2.4 Two Topic Types Per BC

Each bounded context has a command topic (input) and an event topic (output):

| BC | Command topic (input) | Event topic (output) |
|----|----------------------|---------------------|
| **Audio** | `audio_commands` | `audio_events` |
| **Video** | `video_commands` | `video_events` |
| **Source: T3K** | `source_commands` | `source_events` |

All queues live in the single shared database as pgmq queues.

### 2.5 Thick Events

All messages (commands and events) carry rich metadata so consumers have
everything they need without querying back. No thin `{job_id}` messages.

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
  → Updates UI, notifies user via WebSocket
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

### 2.7 Queue Implementation

**Commands (point-to-point):** standard pgmq — `pgmq.read()` → process →
`pgmq.archive()`. One consumer drains the queue. Visibility timeout for retry.

**Events (multi-consumer):** pgmq as append log with consumer offsets:

1. Producer writes via `pgmq.send()` — transactional with domain state.
2. Each consumer maintains its own offset (last processed `msg_id`) in a shared
   `msg_consumer_offsets` table.
3. Consumer polls using its offset from the pgmq queue.
4. After processing: updates offset.
5. Cleanup: periodically archive messages below the minimum offset across all
   registered consumers.

### 2.8 Database Table Layers

| Layer | Tables | Owned by |
|-------|--------|----------|
| BC domain | `core_jobs`, `core_gear`, `core_shootouts`, `t3k_tone_staging`, ... | Specific BC code (import-linter enforced) |
| pgmq queues | `pgmq.q_audio_commands`, `pgmq.q_video_events`, ... | Shared messaging infrastructure |
| Messaging state | `msg_consumer_offsets` | Shared messaging infrastructure |

### 2.9 Worker as Runtime, BCs as Libraries

Audio and video BCs are libraries (`libs/audio`, `libs/video`). They don't run
as separate processes. The worker process:

- Connects to the single database
- Runs pgmq consumer loops (polling)
- Routes messages to BC handler functions
- BC handler code never touches pgmq directly — it receives typed messages
  and does domain work

### 2.10 Token Refresh Ownership

T3K token refresh is handled by the sync consumer as part of its startup
lifecycle. `T3KSyncService` already calls `token_manager.ensure_valid_token()`.
Add proactive refresh if token expires within 10 minutes. Scheduler no longer
proxies token refresh via HTTP.

### 2.11 Worker Import Decoupling (Required)

Move shared ORM models from `webapp.adapters.persistence.models` to
`libs/core`. Worker imports from core instead of webapp. This is required,
not optional.

### 2.12 BC-Level CLAUDE.md Files

Each BC has its own `CLAUDE.md` file pointing to `AGENTS.md` for shared rules,
plus BC-specific rules, table ownership declarations, and implementation
guidelines.

---

## 3. Queue Topology (Target)

### Queues to create

| Queue | Type | Producer(s) | Consumer(s) |
|-------|------|-------------|-------------|
| `audio_commands` | Command | Webapp, Video BC | Audio BC consumer |
| `audio_events` | Event | Audio BC | Video BC, Webapp, monitoring |
| `video_commands` | Command | Webapp | Video BC consumer |
| `video_events` | Event | Video BC | Webapp, monitoring |
| `source_commands` | Command | Scheduler | T3K sync consumer |
| `source_events` | Event | T3K sync service | Gear mapper (worker), monitoring |

### Queues to remove

- `audio_processing` (unused, never wired)
- `video_composition` (unused, never wired)
- `notifications` (unused, never wired)
- `jobs_dead_letter` (unused, never wired)
- `gear_sync` (replaced by `source_events`)
- `gear_pack_sync` (legacy)
- `gear_model_sync` (legacy)
- `sync_dead_letter` (replaced by DLQ convention on new queues)
- `gear_sync_dlq` (replaced by DLQ convention on new queues)

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
| `trigger_sync` | `source_commands` | Scheduler | source name, requested_at |

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
implementation planning):

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

---

## 6. Phase Breakdown (Draft — Needs Detail)

### Phase 0: Documentation baseline

- Write canonical wiki page `Jobs-Architecture-and-Operations.md`
- Refactor existing wiki pages (dedup, link to canonical page)
- Update AGENTS.md (outbox rule, BC communication patterns, table isolation rule)
- Update gts-architecture skill references
- Create/update BC-level CLAUDE.md files with table ownership declarations
- Update memory files

### Phase 1: Single database migration

- Merge `gts_t3k_source` tables into main database
- Rename all tables with BC prefixes (`core_*`, `t3k_*`)
- Update all ORM models, migrations, connection strings
- Simplify Docker compose (one DB init)
- Remove `T3K_DATABASE_URL` from worker/scheduler config
- Update import-linter contracts

### Phase 2: Command and event infrastructure

- Create pgmq queues: `audio_commands`, `audio_events`, `video_commands`,
  `video_events`, `source_commands`, `source_events`
- Create `msg_consumer_offsets` table
- Drop unused/legacy queues
- Build command consumer base (pgmq read/archive pattern)
- Build event consumer base (offset-based read pattern)

### Phase 3: Source sync — migrate to new pattern

- Rename gear_sync flow to `source_commands`/`source_events`
- Fix transactional outbox (publish within transaction, not after commit)
- Scheduler writes to `source_commands` instead of HTTP-calling worker
- Remove scheduler → worker HTTP calls
- Token refresh moves into sync consumer lifecycle

### Phase 4: Audio BC — commands and events

- Implement `audio_commands` consumer in worker
- Refactor audio handlers to consume from queue
- Add thick event publishing to `audio_events` on completion
- Wire `publish_progress` for real-time WebSocket updates

### Phase 5: Video BC — commands and events

- Implement `video_commands` consumer in worker
- Video BC consumes `audio_events` to know when audio is ready
- Video BC publishes to `video_events` on completion
- Webapp creates VIDEO_COMPOSE command instead of HTTP dispatch

### Phase 6: Webapp decoupling and cleanup

- Webapp writes commands to `audio_commands` or `video_commands` + Job row
  (transactional)
- Remove `enqueue_to_worker()` HTTP dispatch
- Worker admin API becomes operator-only tooling
- Remove direct `.kiq()` calls from all handlers

### Phase 7: Worker import decoupling

- Move shared ORM models from `webapp.adapters.persistence.models` to
  `libs/core`
- Worker imports from core instead of webapp
- Update import-linter contracts

---

## 7. Scope Includes

- Source code refactoring and implementation (Phases 1-7)
- Wiki documentation (canonical page + refactoring existing pages)
- AGENTS.md updates (rules, architecture table, patterns)
- BC-level CLAUDE.md files (table ownership, BC-specific rules)
- gts-architecture skill reference updates
- Memory file updates
- .claude and .codex configuration files

---

## 8. Open Questions (For Next Session)

1. **pgmq for events detail**: exact consumer poll implementation — how does
   offset-based reading work with pgmq's underlying table structure? Need to
   prototype.
2. **DLQ strategy**: per-queue DLQs or shared DLQ with routing metadata?
3. **Schema migration strategy**: single Alembic migration for the DB merge +
   rename, or phased?
4. **Table rename completeness**: need to audit ALL tables in both databases to
   build the complete rename map.
5. **Message schema validation**: Pydantic models for commands/events? Where
   do they live?
6. **Existing `core_jobs` table role**: still the user-facing aggregate for
   status/progress? How does it interact with the event-driven flow?
7. **TaskIQ's role**: commands go to pgmq, but CPU-intensive work still needs
   TaskIQ for Redis-backed task execution. How do pgmq consumers delegate to
   TaskIQ?
8. **Progress notification wiring**: which handlers publish to Redis pub/sub
   and at what milestones?
9. **Detailed thick event schemas**: full Pydantic models for each command and
   event type.
10. **Consumer registration**: how do event consumers register and how does
    cleanup know the minimum offset?
11. **What happens to `JobType` enum**: does it map to command types, or is it
    replaced?
12. **Reconciliation pattern**: "are all siblings done?" check — where does this
    logic live in the event-driven model?
