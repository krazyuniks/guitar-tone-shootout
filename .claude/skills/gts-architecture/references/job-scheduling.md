# Job Scheduling (TaskIQ)

Async job scheduler for background processing. Separate from pgmq (gear sync message queue).

## Scope Separation

| System | Purpose | Trigger |
|--------|---------|---------|
| TaskIQ | Scheduled tasks + processing jobs | Scheduler cron, user action |
| pgmq | Gear sync messages (source -> core) | Source adapter publishes |

TaskIQ triggers source adapter sync and handles user-initiated processing. pgmq transports sync messages between source and core databases.

## Job Types

| Job Type | Parent | Purpose |
|----------|--------|---------|
| `SOURCE_SYNC` | -- | Source adapter sync (fetch + download + stage + enqueue) |
| `SHOOTOUT` | -- | Orchestrate shootout creation (parent) |
| `SHOOTOUT_AUDIO` | SHOOTOUT | Process single tone for shootout (child) |
| `VIDEO_COMPOSE` | SHOOTOUT | Generate comparison video (child) |
| `SIGNALCHAIN_AUDIO` | -- | Process chain from library (standalone) |
| `ORPHAN_CLEANUP` | -- | Clean orphaned files from failed transactions |

## Job Hierarchy

Shootout processing uses parent/child jobs:

```
SHOOTOUT (parent)
├── SHOOTOUT_AUDIO (tone A)
├── SHOOTOUT_AUDIO (tone B)
├── SHOOTOUT_AUDIO (tone C)
└── VIDEO_COMPOSE (after all segments complete)
```

Parent job tracks aggregate progress. Child jobs execute independently and report to parent.

## Scheduled Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| `ensure_source_sync_running` | */5 min | Auto-start source sync if not running |
| `monitor_stale_jobs` | */2 min | Detect crashed workers |
| `process_pending_retries` | */2 min | Retry failed jobs |
| `orphan_cleanup` | Daily | Remove orphaned files |
| `scheduler_heartbeat` | */1 min | Health monitoring + lock renewal |

## Job Lifecycle

```
PENDING -> RUNNING -> COMPLETED
              ↓
           FAILED -> RETRY -> RUNNING (up to max_attempts)
              ↓
           DEAD (after max retries)
```

| Status | Description |
|--------|-------------|
| PENDING | Created, waiting for worker |
| RUNNING | Worker executing |
| COMPLETED | Finished successfully |
| FAILED | Error occurred, may retry |
| RETRY | Scheduled for retry |
| DEAD | Exceeded max retries |

## Containers

| Container | Purpose | Admin Port |
|-----------|---------|------------|
| `scheduler` | Triggers scheduled tasks | -- |
| `worker` | Executes jobs + consumes sync messages + admin API | 8001 |

**Worker container runs:**
- Admin API (FastAPI on port 8001) -- serves all admin endpoints
- TaskIQ worker (job execution)
- pgmq consumer (gear sync messages)

The worker serves T3K admin endpoints (`/admin/t3k/*`) by querying `gts_t3k_source` directly -- it already has this database connection for the pgmq consumer.

Scheduler and worker run with `--profile jobs` (main worktree only).

## Distributed Lock

Single scheduler instance enforced via Redis lock:

| Setting | Value |
|---------|-------|
| Lock key | `scheduler:lock` |
| TTL | 60 seconds |
| Renewal | Heartbeat task every minute |

Source sync also uses per-source locks to prevent overlapping runs.

## Heartbeat Monitoring

Workers emit heartbeats during job execution:

| Setting | Value |
|---------|-------|
| Interval | 30 seconds |
| Stale threshold | 2 minutes |

Jobs without heartbeat update beyond threshold are marked failed (crash detection).

## Retry Strategy

Exponential backoff with jitter:

| Attempt | Base Delay | Max Delay |
|---------|------------|-----------|
| 1 | 30s | 30s |
| 2 | 60s | 120s |
| 3 | 120s | 300s |

After max attempts, job moves to DEAD status.

## Progress Reporting

**User-initiated jobs** (SHOOTOUT, SIGNALCHAIN_AUDIO):
- Real-time progress via Redis pub/sub
- WebSocket broadcasts to subscribed clients
- Live progress display in UI

**System jobs** (SOURCE_SYNC, ORPHAN_CLEANUP):
- Observability stack (metrics, logs, traces)
- Managed via worker admin API (CLI planned)

## Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max attempts | 3 | Balance reliability and resource usage |
| Heartbeat interval | 30s | Detect crashes without excessive overhead |
| Stale threshold | 2 min | Allow for slow operations |
| Concurrency | 4 workers | Match available CPU cores |
