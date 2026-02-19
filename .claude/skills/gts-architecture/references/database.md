# Database

Single PostgreSQL instance hosting all bounded context tables with BC-prefixed naming.

## Single Database Architecture

All BCs share one PostgreSQL database (`gts_core`). BC separation enforced via:
- **Table naming:** `core_*`, `t3k_*` prefixes
- **Import-linter:** Each BC's ORM models only reference their own tables
- **ORM isolation:** Each BC has its own SQLAlchemy Base class

| Prefix | Bounded Context | Connects From |
|--------|----------------|---------------|
| `core_*` | Core domain | Webapp |
| `t3k_*` | T3K source staging | T3K-sync |
| `msg_*` | Messaging infrastructure | All containers |

## Core Tables (`core_*`)

| Category | Tables |
|----------|--------|
| User | `core_users`, `core_user_identities`, `core_oauth_providers` |
| Unified Gear | `core_gear`, `core_gear_models`, `core_gear_sources`, `core_gear_tags`, `core_gear_makes`, `core_user_gear` |
| Signal Chains | `core_signal_chains`, `core_signal_chain_blocks`, `core_signal_chain_groups`, `core_block_types` |
| Audio | `core_di_tracks`, `core_audio_segments`, `core_shootouts`, `core_shootout_chains` |
| System | `core_jobs`, `core_user_notifications`, `core_audit_logs` |
| Taxonomy | `core_tags`, `core_user_tags`, `core_presets` |

## T3K Source Tables (`t3k_*`)

| Category | Tables |
|----------|--------|
| Staging | `t3k_users_staging`, `t3k_tones_staging`, `t3k_models_staging` |
| Sync | `t3k_sync_checkpoints` |

Source tables are owned by the T3K source adapter. Core domain model has no knowledge of source table structure.

## Messaging Tables

| Table | Purpose |
|-------|---------|
| `msg_consumer_offsets` | Event consumer offset tracking (consumer_id + queue_name -> last_processed_id) |
| `pgmq.q_*` | pgmq queue tables (managed by pgmq extension) |

## pgmq Queues

All queues live in the `pgmq` schema within `gts_core`:

| Queue | Type | Purpose |
|-------|------|---------|
| `audio_commands` | Command | Audio processing requests |
| `video_commands` | Command | Video composition requests |
| `audio_events` | Event | Audio processing results |
| `video_events` | Event | Video composition results |
| `source_events` | Event | Gear sync records from sources |
| `dead_letter` | DLQ | Failed messages for investigation |

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

## Transactional Outbox

All pgmq publishes MUST happen within the same database transaction as the domain state change. This is possible because queues and domain tables share the same database.

```python
async with session.begin():
    session.add(job)
    await session.execute(
        sa.text("SELECT pgmq.send(:queue, CAST(:msg AS jsonb))"),
        {"queue": "video_commands", "msg": json.dumps(command)},
    )
```

## Alembic

Single Alembic migration chain manages all tables (core + t3k + messaging). Located at `infrastructure/migrations/`.

Both webapp Base and T3K Base are registered in `env.py` for autogenerate support.
