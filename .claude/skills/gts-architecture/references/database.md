# Database

PostgreSQL server with separate logical databases per bounded context.

## Database Separation

| Database | Connects From | Purpose |
|----------|---------------|---------|
| `gts_core` | Webapp, Worker | Core domain model (users, gear, signal chains, audio) |
| `gts_t3k_source` | T3K Adapter, Worker | T3K source staging + pgmq queue |

**Isolation rule:** Webapp has NO connection to source databases. Source adapters have NO connection to core database.

Worker is the only component with connections to both -- it consumes from source queues and writes to core database.

## Transactional Send

Each source database has its own pgmq queue. Source adapter writes staging data + enqueues sync record in single transaction. Worker consumes and upserts to core database.

## Core Database Tables (`gts_core`)

| Category | Tables |
|----------|--------|
| User | `users`, `user_identities`, `oauth_providers` |
| Unified Gear | `gear`, `gear_models`, `gear_sources`, `gear_tags`, `gear_makes`, `user_gear` |
| Signal Chains | `signal_chains`, `signal_chain_blocks`, `signal_chain_groups`, `signal_chain_group_amps`, `signal_chain_group_irs`, `block_types` |
| Audio | `di_tracks`, `audio_segments`, `shootouts`, `shootout_chains` |
| System | `jobs`, `error_reports`, `user_notifications`, `audit` |
| Sync | `sources`, `source_checkpoints` |

## Source Database Tables (`gts_t3k_source`)

| Category | Tables |
|----------|--------|
| T3K Staging | `packs`, `models`, `creators`, `tags`, `makes`, `pack_images`, `pack_links` |

Source tables are owned by the source adapter. Core domain model has no knowledge of source table structure.

## Schema Evolution

Core owns synchronisation record schemas and compatibility rules.

**Compatibility Policy:**
- Default: backward-compatible changes (additive)
- Schema changes validated in CI prior to deployment
- Removals require deprecation windows with advance notice

**Zero-Downtime Expand-Contract Pattern** (for breaking changes):

| Phase | Action | Rollback |
|-------|--------|----------|
| **Expand** | Add new column/structure alongside old; deploy dual-write code | Drop new column, revert code |
| **Migrate** | Backfill existing data to new structure (in batches) | Re-run backfill |
| **Contract** | Deploy read-from-new code; stop writing to old; remove old structure after confidence period | Restore from backup (point of no return) |

Each phase is independently deployable. Non-breaking changes (adding nullable columns, new tables, new indexes) can be deployed directly without consumer pause.

**Handling In-Flight Messages:**
1. Deploy consumers that accept both old and new schema formats
2. Deploy sources sending new format
3. After drain period, remove old format handling

In a monorepo, schema changes can be atomic: single change updates core schema + all source adapters. CI validates all adapters conform before merge.

## Message Queue (pgmq)

PostgreSQL-native queue for gear sync pipeline. Each source database hosts its own pgmq queue.

### Queue Location

| Database | Queue | Producer | Consumer |
|----------|-------|----------|----------|
| `gts_t3k_source` | `gear_sync` | T3K Adapter | Worker |
| `gts_aidax_source` | `gear_sync` | AIDA-X Adapter | Worker |

**Why queues in source databases?** Enables transactional send -- source adapter writes staging data and enqueues sync record in single transaction. No outbox pattern needed.

Worker polls from all source database queues, consuming messages and upserting to core database.

### Topic Structure

One topic per aggregate (not per source):

```
gear_sync
```

Source identity embedded in message payload (`source_name` field). Each source database has the same queue name; worker connects to each database separately.

### Message Schema

Messages conform to `GearSyncRecord` (defined in `libs/core/records/`):

| Field | Type | Description |
|-------|------|-------------|
| `source_name` | string | Source identifier (e.g., "t3k") |
| `source_record_id` | string | ID from source system |
| `source_updated_at` | datetime | Timestamp from source |
| `operation` | enum | CREATE, UPDATE, DELETE |
| `payload` | object | Gear data in core schema |

Core owns this schema. Source adapters import and conform to it.

### Consumer Pattern

Worker polls each source database queue:

1. `pgmq.read_with_poll()` with visibility timeout
2. Validate message against `GearSyncRecord` schema
3. Upsert to core database (idempotent)
4. `pgmq.archive()` on success

```sql
-- Read batch with 60s visibility timeout
SELECT * FROM pgmq.read_with_poll('gear_sync', vt => 60, qty => 10);

-- Archive after successful processing
SELECT pgmq.archive('gear_sync', msg_ids => ARRAY[1, 2, 3]);
```

### Dead Letter Queue

pgmq tracks read attempts via `read_ct` field. Worker implements automatic DLQ:

1. On read, check `read_ct` against max retries threshold
2. If exceeded, move message to `gear_sync_dlq` queue
3. Archive from main queue

```sql
-- Move to DLQ when read_ct exceeds threshold
INSERT INTO pgmq.q_gear_sync_dlq (msg)
SELECT msg FROM pgmq.q_gear_sync WHERE msg_id = $1;

SELECT pgmq.archive('gear_sync', msg_id => $1);
```

DLQ messages retain original payload plus failure metadata for investigation.

### Delivery Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| At-least-once | Messages reappear after visibility timeout if not archived |
| Idempotent consumers | Upsert with `(source_name, source_record_id, source_updated_at)` |
| Order preserved | Single consumer per source database |

### pgmq Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Visibility timeout (`vt`) | 60s | Processing time without blocking |
| Max retries | 3 | Balance reliability and throughput |
| Poll interval | 1s | Responsive without excessive load |
| Batch size (`qty`) | 10 | Small batches for responsiveness |

### Migration Path

Current: pgmq in PostgreSQL (simple, transactional).

**Scaling triggers** -- Consider migration when any of:
- Throughput exceeds ~10k messages/second sustained
- Operational risk isolation required (source failure affecting core)
- Organisational boundaries emerge (team ownership of source adapters)
- Broker features needed (fan-out, replay, cross-DC replication)

**Note:** Scaling is an optional migration path, not a near-term driver.

**Migration to outbox pattern:**
1. Add outbox table to each source database
2. Replace direct queue send with outbox insert in same transaction
3. Deploy outbox workers per source
4. Switch to external broker (e.g., RabbitMQ, SQS)
5. Core consumer logic unchanged (same message schema)
