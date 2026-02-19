# Bounded Context Architecture Plan

## Summary

The current system has three logical bounded contexts (Core Domain, Source: T3K, Execution) but the boundaries are not enforced at the infrastructure level. The worker service straddles every context, the `jobs` table is a shared monolith, and inter-service communication is synchronous HTTP RPC where it should be transactional event handoff.

This plan establishes correct bounded context ownership, event-driven communication via pgmq (already deployed), and a phased migration that preserves the existing behaviour at each step.

---

## 1. Current Architecture (As-Is)

### Bounded contexts

| Context | Library | App | Database | Docker service |
|---------|---------|-----|----------|----------------|
| Core domain | `libs/core` | `webapp` | `gts_core` | `webapp` (8000) |
| Source: T3K | `sources/t3k` | — | `gts_t3k_source` | — |
| Audio processing | `libs/audio` | — | — | — |
| Video rendering | `libs/video` | — | — | `video` (8002) |
| Execution | — | `worker` | **both** | `worker` (8001) |
| Scheduling | — | `scheduler` | `gts_core` (raw SQL) | `scheduler` |

### Cross-boundary violations

1. **Worker imports `webapp.adapters.persistence.models.*`** — 18+ ORM models used directly; no import-linter contract prevents this.
2. **Worker imports `source_t3k`** — sync service, token manager, publisher all accessed directly from worker task handlers.
3. **Worker connects to both databases** — `gts_core` and `gts_t3k_source` sessions in the same process.
4. **Worker creates SOURCE_SYNC jobs in `gts_core.jobs`** — source-domain operational state stored in core's job ledger.
5. **Scheduler HTTP-calls worker admin** — for job dispatch, sync triggering, and token refresh.
6. **Webapp HTTP-calls worker admin** — synchronous dispatch in user request path.

### Communication patterns

| Flow | Mechanism | Problem |
|------|-----------|---------|
| Webapp -> "run this job" | HTTP POST `worker:8001/api/admin/enqueue` | User request depends on worker availability |
| Scheduler -> "trigger sync" | HTTP POST `worker:8001/api/admin/sources/t3k/sync` | RPC coupling; scheduler has source-domain knowledge |
| Scheduler -> "re-enqueue stuck job" | HTTP POST `worker:8001/api/admin/enqueue` | Recovery loop exists only because dispatch is unreliable |
| Scheduler -> "refresh token" | HTTP POST `worker:8001/api/admin/auth/refresh-t3k` | Scheduler proxying source-domain auth lifecycle |
| Source sync -> gear mapper | pgmq `gear_sync` in `gts_t3k_source` | **Correct pattern** — only event-driven flow |
| Worker -> browser progress | Redis pub/sub -> WebSocket | Fine for real-time push |

### The jobs table: a shared monolith

All job types live in one `jobs` table in `gts_core`, regardless of which BC owns them:

| JobType | Domain owner | Created by | Correct placement? |
|---------|-------------|------------|-------------------|
| `SHOOTOUT` | Core | webapp | Yes |
| `SHOOTOUT_AUDIO` | Core | worker | Yes |
| `SHOOTOUT_MASTER` | Core | worker | Yes |
| `SOURCE_SYNC` | Source: T3K | worker admin | **No** — source operational state in core |
| `GEAR_SYNC` | Source: T3K | (unused) | **No** |
| `MODEL_DOWNLOAD` | Source: T3K | (unused) | **No** |
| `IR_DOWNLOAD` | Source: T3K | (unused) | **No** |
| `NOTIFICATION` | Core | (unused) | Acceptable |
| `AUDIO_PROCESSING` | Core | (unused) | Acceptable |
| `VIDEO_COMPOSE` | Core | (unused) | Acceptable |

---

## 2. Target Architecture (To-Be)

### Design principles

1. **Each BC owns its own operational state.** Job tracking, attempt counts, locks, and status live in the BC's own database.
2. **Communication is event-driven via pgmq.** Transactional outbox pattern: write state + enqueue intent in one DB transaction.
3. **The worker is a stateless executor.** It never creates jobs. It consumes intents from queues, executes tasks, and writes results back.
4. **The scheduler produces intents, not HTTP calls.** It writes messages to queues in the appropriate BC's database.
5. **The admin API is for operators only.** Not part of normal request flow. Manual retry, cancel, inspection.

### Bounded context ownership

```
┌──────────────────────────────────────────┐
│  Core Domain                             │
│  App: webapp (port 8000)                 │
│  DB: gts_core                            │
│                                          │
│  Owns:                                   │
│    - Users, gear, shootouts, signal      │
│      chains, DI tracks, presets, tags    │
│    - Core job types: SHOOTOUT,           │
│      SHOOTOUT_AUDIO, SHOOTOUT_MASTER,    │
│      AUDIO_PROCESSING, VIDEO_COMPOSE,    │
│      NOTIFICATION                        │
│    - pgmq: job_dispatch_intent           │
│                                          │
│  Publishes:                              │
│    - job_dispatch_intent (pgmq,          │
│      transactional with job row)         │
│                                          │
│  Consumes:                               │
│    - gear_synced (from source BC,        │
│      via worker gear mapper)             │
│                                          │
│  Does NOT know about:                    │
│    - Worker URLs, TaskIQ, Redis broker   │
│    - Source sync internals               │
│    - How or where tasks execute          │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Source: T3K                             │
│  Library: sources/t3k                    │
│  DB: gts_t3k_source                      │
│                                          │
│  Owns:                                   │
│    - T3K API client, auth, staging       │
│    - Sync job tracking (new table:       │
│      sync_jobs in gts_t3k_source)        │
│    - Sync lock, checkpoints, rate        │
│      limiting, circuit breaker           │
│    - pgmq: sync_trigger, gear_sync       │
│                                          │
│  Publishes:                              │
│    - gear_sync (already exists)          │
│                                          │
│  Consumes:                               │
│    - sync_trigger (from scheduler or     │
│      operator tooling)                   │
│                                          │
│  Does NOT know about:                    │
│    - gts_core.jobs                       │
│    - Webapp, worker, or scheduler        │
│    - How gear_sync events are consumed   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Execution (Worker)                      │
│  App: worker (port 8001 admin only)      │
│  DB: none of its own                     │
│  Broker: TaskIQ + Redis                  │
│                                          │
│  Role: stateless task execution          │
│                                          │
│  Consumes:                               │
│    - job_dispatch_intent (gts_core       │
│      pgmq) -> dispatches TaskIQ tasks    │
│    - sync_trigger (gts_t3k_source        │
│      pgmq) -> runs T3K sync             │
│    - gear_sync (gts_t3k_source pgmq)    │
│      -> maps gear into gts_core         │
│                                          │
│  Writes back to:                         │
│    - gts_core (job status, gear data)    │
│    - gts_t3k_source (sync job status,    │
│      checkpoints)                        │
│                                          │
│  Does NOT:                               │
│    - Create jobs                         │
│    - Own any tables                      │
│    - Make architectural decisions about  │
│      what to run or when                 │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Scheduling                              │
│  App: scheduler                          │
│  DB: reads gts_core (monitoring only)    │
│                                          │
│  Role: time-based intent production      │
│                                          │
│  Publishes:                              │
│    - sync_trigger to gts_t3k_source      │
│      pgmq (replaces HTTP call)           │
│                                          │
│  Monitors:                               │
│    - Stale jobs in gts_core              │
│      (heartbeat-based, existing logic)   │
│    - Pending retries in gts_core         │
│      (existing logic)                    │
│                                          │
│  Does NOT:                               │
│    - HTTP-call worker for dispatch       │
│    - Know about source auth lifecycle    │
│    - Create or own jobs                  │
└──────────────────────────────────────────┘
```

### Event/queue topology

All queues use pgmq. Transactional send where possible (same DB transaction as state change).

| Queue | Database | Producer | Consumer | Payload |
|-------|----------|----------|----------|---------|
| `job_dispatch_intent` | `gts_core` | webapp (transactional with job INSERT) | worker intent consumer | `{job_id, job_type, created_at}` |
| `sync_trigger` | `gts_t3k_source` | scheduler (periodic) | worker sync handler | `{source: "t3k", requested_at}` |
| `gear_sync` | `gts_t3k_source` | source sync (already exists) | worker gear mapper (already exists) | `GearSyncRecord` (already defined) |
| `gear_sync_dlq` | `gts_t3k_source` | gear mapper on failure (already exists) | manual inspection | error + original message |
| `job_dispatch_intent_dlq` | `gts_core` | intent consumer on failure | manual inspection | error + original intent |

### Message contracts

**job_dispatch_intent:**

```json
{
  "job_id": "uuid",
  "job_type": "shootout|shootout_audio|shootout_master|audio_processing|video_compose",
  "created_at": "2026-02-19T12:00:00Z",
  "version": 1
}
```

Idempotency: consumer checks `jobs.task_id IS NULL AND status IN (pending, queued)` before dispatch. Already-dispatched jobs are no-ops (archive message).

**sync_trigger:**

```json
{
  "source": "t3k",
  "requested_at": "2026-02-19T12:00:00Z",
  "version": 1
}
```

Idempotency: consumer checks Redis lock `t3k:sync:lock` before starting. If lock exists, archives message (sync already running). Consumer creates sync job in `gts_t3k_source.sync_jobs`, not in `gts_core.jobs`.

### What changes in each Docker service

| Service | Current role | Target role | Changes |
|---------|-------------|-------------|---------|
| `webapp` | Job creation + HTTP dispatch | Job creation + pgmq intent publish | Remove `enqueue_to_worker()`. Add transactional pgmq send in job creation path. |
| `worker` | God service (admin API + TaskIQ + consumers) | Stateless executor + pgmq consumers | Add `job_dispatch_intent` consumer. Move SOURCE_SYNC job creation into sync consumer. Remove job creation from admin API. |
| `scheduler` | HTTP-calls worker for everything | Intent producer + DB monitor | Replace HTTP calls with pgmq writes. Remove source-auth proxy. Keep stale-job and retry monitoring. |
| `video` | HTTP render API | No change | Already correctly isolated. |
| `db` | pgmq already installed | No change | Just create new queues via migration. |
| `redis` | TaskIQ broker + pub/sub + locks | No change | Same role. |

---

## 3. Migration Plan

### Phase 1: Core job dispatch intent queue

**Goal:** Webapp stops HTTP-calling worker for job dispatch. Worker consumes intents from pgmq instead.

**Steps:**

1. Create pgmq queue `job_dispatch_intent` in `gts_core` (Alembic migration).
   - Note: `init-pgmq.sql` already creates unused queues (`audio_processing`, `video_composition`, `notifications`, `jobs_dead_letter`). Evaluate whether to repurpose `jobs_dead_letter` as the DLQ or create `job_dispatch_intent_dlq` explicitly. Clean up unused queues.
2. Implement `JobIntentConsumer` in worker — polls `job_dispatch_intent` from `gts_core` DB, dispatches TaskIQ by job type, archives on success, DLQs on failure.
3. Add transactional pgmq send in webapp's job creation path — same transaction as job INSERT.
4. Dual-run: both HTTP dispatch and intent consumer active. Consumer is idempotent (checks `task_id` before dispatch).
5. Validate: all jobs dispatch correctly via consumer. Monitor intent queue depth, DLQ count.
6. Remove `enqueue_to_worker()` from webapp. Remove HTTP dispatch from user request paths.
7. Update scheduler's `dispatch_pending_jobs` — either remove it (consumer handles dispatch) or reduce scope to monitoring only (alert on stuck jobs, don't re-dispatch).

**Exit criteria:**
- Webapp creates jobs without any HTTP call to worker.
- Worker intent consumer processes all core job types.
- No job dispatch depends on worker admin API availability.

**Risks:**
- Duplicate dispatch during dual-run. Mitigated by idempotent consumer.
- Consumer lag. Mitigated by pgmq polling interval (1-5s) and queue depth monitoring.

### Phase 2: Source sync ownership transfer

**Goal:** SOURCE_SYNC job tracking moves from `gts_core.jobs` to `gts_t3k_source`. Sync triggering moves from HTTP RPC to pgmq intent.

**Steps:**

1. Create `sync_jobs` table in `gts_t3k_source` (Alembic migration on t3k source DB).
   - Columns: `id`, `status`, `started_at`, `completed_at`, `error`, `attempt`, `stats` (JSON — tones synced, models downloaded, etc.).
   - This is simpler than the core `jobs` table — source sync has no parent/child hierarchy, no user ownership, no TaskIQ task_id.
2. Create pgmq queue `sync_trigger` in `gts_t3k_source`.
3. Implement sync trigger consumer in worker — polls `sync_trigger`, checks Redis lock, creates `sync_jobs` row in `gts_t3k_source`, runs `T3KSyncService`, updates `sync_jobs` status.
4. Modify scheduler's `ensure_source_sync_running` — replace HTTP POST to worker with pgmq send to `sync_trigger` queue in `gts_t3k_source`. Scheduler needs a `gts_t3k_source` DB connection for this (it currently only connects to `gts_core`).
5. Remove SOURCE_SYNC job creation from worker admin API (`trigger_sync` endpoint).
6. Remove `SOURCE_SYNC` from `gts_core.jobs` — stop writing new rows. Keep old rows for historical queries if needed, or migrate/archive them.
7. Remove `JobType.SOURCE_SYNC` exclusion from scheduler's `dispatch_pending_jobs` (no longer relevant).

**Exit criteria:**
- No SOURCE_SYNC rows written to `gts_core.jobs`.
- Sync lifecycle fully tracked in `gts_t3k_source.sync_jobs`.
- Scheduler triggers sync via pgmq, not HTTP.

**Risks:**
- Scheduler needs a second DB connection (`gts_t3k_source`). Acceptable — it's a single pgmq write, not complex queries.
- Historical sync job data in `gts_core.jobs` becomes orphaned. Mitigated by keeping old rows read-only or migrating to `sync_jobs`.

### Phase 3: Scheduler HTTP decoupling

**Goal:** Remove all scheduler -> worker HTTP calls. Scheduler communicates only via DB writes (pgmq, raw SQL).

**Steps:**

1. Sync triggering already moved to pgmq in Phase 2.
2. Token refresh: move T3K token refresh responsibility into the source BC.
   - Option A: Source sync consumer handles token refresh as part of its startup (already partially true — `T3KSyncService` calls `token_manager.ensure_valid_token()`).
   - Option B: Separate scheduled task within worker that handles source auth lifecycle.
   - Either way, scheduler no longer needs to HTTP-call `POST /api/admin/auth/refresh-t3k`.
3. `dispatch_pending_jobs` recovery sweep:
   - After Phase 1, the intent consumer handles dispatch. The recovery sweep becomes redundant for normal flow.
   - Keep a simplified version as a monitoring/alerting task: if jobs are PENDING for >10 minutes, emit an alert (log warning, metric) rather than attempting HTTP re-dispatch.
   - Or: re-enqueue to `job_dispatch_intent` pgmq queue directly (scheduler already has `gts_core` DB access).
4. Remove all `httpx` / HTTP client usage from scheduler.

**Exit criteria:**
- Scheduler has zero HTTP calls to worker.
- Scheduler's only external dependencies: `gts_core` DB, `gts_t3k_source` DB, Redis (for lock).
- All scheduler actions are DB writes or DB reads.

**Risks:**
- Token refresh timing. If moved to sync-consumer startup, tokens could expire between sync runs (currently 60s cycle, so low risk). Add a TTL check in the consumer that refreshes proactively if token expires within 10 minutes.

### Phase 4: Worker admin API simplification

**Goal:** Worker admin API becomes pure operator tooling. No domain dispatch logic.

**Steps:**

1. Remove `POST /api/admin/enqueue` as a dispatch mechanism used by other services.
   - Keep for manual operator use (admin can manually push a specific job to TaskIQ for debugging).
   - Clearly mark as operator-only in code and docs.
2. Remove `POST /api/admin/sources/t3k/sync` trigger endpoint.
   - Replace with: operator can write to `sync_trigger` pgmq queue via admin API (or a CLI tool).
3. Remove `POST /api/admin/auth/refresh-t3k` proxy endpoint.
4. Evaluate remaining admin endpoints — keep those that are genuinely operator tooling:
   - `GET /api/admin/jobs` — list/filter jobs (useful).
   - `GET /api/admin/jobs/{id}` — inspect job (useful).
   - `POST /api/admin/jobs/{id}/cancel` — operator cancel (useful).
   - `POST /api/admin/jobs/{id}/retry` — operator retry (useful, but should write to pgmq intent queue rather than direct TaskIQ dispatch).
   - `GET /api/admin/health` — health check (useful).
   - Admin unlock endpoints — keep for ops (useful).

**Exit criteria:**
- No service-to-service communication flows through admin API.
- Admin API is exclusively for human operators and scripts.

### Phase 5: Worker import decoupling (optional, lower priority)

**Goal:** Reduce worker's direct dependency on `webapp.adapters.persistence.models`.

This phase is optional and lower priority because the current coupling is a code organisation smell, not a correctness problem. The worker and webapp share a database — the ORM models are just table mappings.

**Possible approaches:**

- **Move shared ORM models to `libs/core`** — the Job, Gear, Shootout models become part of core's persistence layer rather than webapp's. Core gains an `adapters/persistence/` package. Worker imports from core instead of webapp.
- **Create a shared persistence library** — `libs/persistence` with models for `gts_core` tables. Both webapp and worker import from it.
- **Leave as-is** — accept the coupling as pragmatic for a single-team project. Add an import-linter contract to at least document and limit which webapp models the worker can use.

**Recommendation:** Defer this until after Phases 1-4. If the project grows to multiple source BCs or multiple worker types, revisit.

---

## 4. Operational Considerations

### Observability

| Metric | Source | Alert threshold |
|--------|--------|----------------|
| `job_dispatch_intent` queue depth | pgmq query | > 50 messages for > 2 minutes |
| `job_dispatch_intent_dlq` count | pgmq query | > 0 (any DLQ entry is actionable) |
| `sync_trigger` queue depth | pgmq query | > 5 (should process within seconds) |
| `gear_sync` queue depth | pgmq query (already exists) | > 100 |
| Intent-to-TaskIQ latency | consumer timestamp diff | > 10 seconds |
| Jobs stuck in PENDING > 10 min | gts_core SQL | > 0 |

### Failure modes

| Failure | Impact | Recovery |
|---------|--------|----------|
| Worker down | Intents accumulate in pgmq (durable in DB) | Worker restart drains queue automatically |
| Redis down | TaskIQ dispatch fails; consumer retries with backoff | Consumer keeps retrying; intents not lost |
| DB down | Everything stops | Standard DB recovery; no data loss |
| Consumer crash | Visibility timeout expires; message becomes visible again | pgmq re-delivers automatically |
| Poison message | Repeated failures | DLQ after max retries; alert fires |

### Runbook additions

1. **Intent queue backed up** — check worker logs, verify consumer is running, check Redis connectivity.
2. **DLQ entries** — inspect message payload, check job status in DB, fix root cause, replay from DLQ.
3. **Sync not triggering** — check `sync_trigger` queue depth, check Redis lock `t3k:sync:lock`, check scheduler logs.

---

## 5. What This Plan Does NOT Cover

- **Multi-source expansion** (adding sources beyond T3K). The pattern supports it — each source gets its own DB, sync_jobs table, and pgmq queues — but the specifics are out of scope.
- **Worker horizontal scaling** (multiple worker instances). pgmq visibility timeout already supports competing consumers, but TaskIQ broker configuration for multiple workers is a separate concern.
- **Video rendering pipeline.** The video service is already correctly isolated behind an HTTP API. Its dispatch will use `job_dispatch_intent` like other core job types.
- **WebSocket/real-time progress.** Redis pub/sub for job progress is fine and orthogonal to this plan.

---

## 6. Sequencing and Dependencies

```
Phase 1: Core job dispatch intent queue
  ├── No external dependencies
  ├── Can start immediately
  └── Unblocks Phase 3 (scheduler dispatch removal)

Phase 2: Source sync ownership transfer
  ├── No dependency on Phase 1 (separate BC, separate DB)
  ├── Can run in parallel with Phase 1
  └── Unblocks Phase 3 (scheduler sync trigger removal)

Phase 3: Scheduler HTTP decoupling
  ├── Blocked by Phase 1 (dispatch_pending_jobs removal)
  ├── Blocked by Phase 2 (sync trigger removal)
  └── Unblocks Phase 4

Phase 4: Worker admin API simplification
  ├── Blocked by Phase 3 (all HTTP callers removed)
  └── Final cleanup

Phase 5: Worker import decoupling (optional)
  ├── Independent of Phases 1-4
  └── Can be done any time; lowest priority
```

Phases 1 and 2 can run in parallel. Phases 3 and 4 are sequential gates.

---

## 7. Relationship to Existing Plan

The original `docs/plans/2026-02-19-core-job-dispatch-decoupling.md` covers Phase 1 of this plan. Its problem statement, target pattern, and message contract are correct. This plan supersedes it by:

1. Adding source sync ownership transfer (Phase 2).
2. Adding scheduler HTTP decoupling (Phase 3).
3. Adding worker admin simplification (Phase 4).
4. Correcting the claim that T3K source sync uses transactional queueing (it doesn't — the publish is after commit).
5. Specifying database placement, consumer deployment model, and operational details.
6. Providing a dependency graph showing which phases can parallelise.
