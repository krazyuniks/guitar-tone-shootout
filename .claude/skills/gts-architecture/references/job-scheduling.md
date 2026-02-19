# Job Scheduling & Event-Driven Messaging

Event-driven architecture using pgmq for all inter-BC communication. No TaskIQ, no Redis, no scheduler.

> **Canonical reference:** [[Jobs-Architecture-and-Operations]] wiki page.

## Container Topology

| Container | Purpose | Consumes | Produces |
|-----------|---------|----------|----------|
| `webapp` | User API + event consumers | `source_events`, `audio_events`, `video_events` | `audio_commands`, `video_commands` |
| `t3k-sync` | Eternal sync loop | -- | `source_events` |
| `audio-worker` | Audio processing | `audio_commands` | `audio_events` |
| `video-worker` | Video composition | `video_commands`, `audio_events` | `video_events`, `audio_commands` |

All containers share one PostgreSQL database (`gts_core`). BC isolation via import-linter + table naming.

## Queue Topology

| Queue | Type | Purpose |
|-------|------|---------|
| `audio_commands` | Command (point-to-point) | Audio processing requests |
| `video_commands` | Command (point-to-point) | Video composition requests |
| `audio_events` | Event (multi-consumer) | Audio processing results |
| `video_events` | Event (multi-consumer) | Video composition results |
| `source_events` | Event (multi-consumer) | Gear sync records from sources |
| `dead_letter` | DLQ (shared) | Failed messages for investigation |

## Message Types

**Commands** (point-to-point, consumed once):
- `process_chain_audio` — process a single signal chain's audio
- `produce_master_track` — mix all chain segments into master
- `compose_shootout` — orchestrate full shootout video

**Events** (multi-consumer via offset tracking):
- `chain_audio_complete` — single chain audio finished
- `master_track_complete` — master track finished
- `video_compose_complete` — video rendering finished
- `gear_synced` — gear data synced from source

## Consumer Patterns

### Command Consumer (point-to-point)

Uses `pgmq.read_with_poll()` with visibility timeout. Messages archived after processing. Dead-lettered after max retries.

```python
# CommandConsumer base class in infra/messaging/
result = await session.execute(
    sa.text("SELECT * FROM pgmq.read_with_poll(:queue, :vt, :qty)"),
    {"queue": queue_name, "vt": 60, "qty": 10},
)
```

### Event Consumer (multi-consumer)

Uses offset tracking via `msg_consumer_offsets` table. Each consumer reads independently by tracking its last processed message ID. Messages are NOT deleted — they're archived by a periodic janitor.

```python
# EventConsumer base class in infra/messaging/
# Each consumer has a unique consumer_id (e.g., "webapp:audio_events")
# Reads messages with msg_id > last_processed_id
```

## Transactional Outbox

All pgmq publishes MUST happen within the same database transaction as the domain state change:

```python
# CORRECT: same transaction
async with session.begin():
    session.add(job)
    await session.execute(
        sa.text("SELECT pgmq.send(:queue, CAST(:msg AS jsonb))"),
        {"queue": "video_commands", "msg": json.dumps(command)},
    )

# WRONG: separate transaction
await session.commit()  # domain state committed
await publish(command)   # message could be lost if this fails
```

## Job Types

| Job Type | Queue | Purpose |
|----------|-------|---------|
| `SHOOTOUT` | -- | Parent job (webapp creates, tracks progress) |
| `SHOOTOUT_AUDIO` | `audio_commands` | Process single tone for shootout |
| `VIDEO_COMPOSE` | `video_commands` | Generate comparison video |
| `SIGNALCHAIN_AUDIO` | `audio_commands` | Process chain from library |
| `ORPHAN_CLEANUP` | -- | Clean orphaned files (webapp background task) |

`SOURCE_SYNC` is eliminated — t3k-sync is self-driven.

## Job Lifecycle

```
PENDING -> RUNNING -> COMPLETED
              |
           FAILED -> RETRY -> RUNNING (up to max_attempts)
              |
           DEAD (after max retries)
```

Job status updates come from event consumers in the webapp (not from workers directly).

## Background Tasks (Webapp)

| Task | Schedule | Purpose |
|------|----------|---------|
| `monitor_stale_jobs` | */2 min | Detect crashed workers |
| `process_pending_retries` | */2 min | Retry failed jobs |
| `event_queue_janitor` | Hourly | Archive processed event messages |

## Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max retries (commands) | 5 | Balance reliability and resource usage |
| Visibility timeout | 60s | Processing time without blocking |
| Poll interval | 1s | Responsive without excessive load |
| Batch size | 10 | Small batches for responsiveness |
