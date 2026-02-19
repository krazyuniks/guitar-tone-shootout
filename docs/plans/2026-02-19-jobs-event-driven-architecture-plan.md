# Jobs & Event-Driven Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor GTS from a monolithic worker with TaskIQ/Redis to an event-driven architecture with one container per bounded context, pgmq-only messaging, and transactional outbox.

**Architecture:** Each BC (Core/Webapp, Audio, Video, Source:T3K) runs as its own Docker container communicating via pgmq commands and events. A single PostgreSQL database hosts all tables (BC-prefixed) and all pgmq queues. TaskIQ, Redis, the monolithic worker, and the scheduler are eliminated.

**Tech Stack:** PostgreSQL 18 + pgmq, FastAPI, SQLAlchemy 2.0, Pydantic v2, Docker Compose, Alembic

**Design doc:** `docs/plans/2026-02-19-jobs-event-driven-architecture-design.md`
**Wiki reference:** `../wiki/Jobs-Architecture-and-Operations.md`

---

## Phase 0: Documentation Baseline

> Update documentation and agent instructions to reflect the target architecture.
> No code changes. System continues working as-is after this phase.

### Task 0.1: Update AGENTS.md with new architecture rules

**Files:**
- Modify: `AGENTS.md`

**Steps:**

1. Read current AGENTS.md architecture table (Module dependency matrix).

2. Update the Architecture module table to reflect target container topology:
   - Replace `worker` row with `audio-worker`, `video-worker`, `t3k-sync` rows
   - Remove `scheduler` row
   - Update dependency descriptions

3. Add new rules to the Architecture section:
   - **Transactional outbox rule:** "All pgmq publishes MUST happen within the same database transaction as the domain state change."
   - **BC table isolation rule:** "Each BC's ORM models MUST only reference their own BC's tables (prefixed `core_*`, `t3k_*`, etc.)."
   - **Single database rule:** "All BCs share one PostgreSQL instance. BC separation via import-linter + table naming."

4. Update Infrastructure section:
   - Remove references to Redis
   - Remove references to scheduler container
   - Update `--profile jobs` description to reflect new containers

5. Commit: `docs(agents): update architecture rules for event-driven design`

### Task 0.2: Update gts-architecture skill references

**Files:**
- Modify: `.claude/skills/gts-architecture/references/job-scheduling.md`
- Modify: `.claude/skills/gts-architecture/references/infrastructure.md`
- Modify: `.claude/skills/gts-architecture/references/database.md`

**Steps:**

1. Read each reference file.

2. Update `job-scheduling.md`:
   - Replace TaskIQ content with pgmq consumer loop architecture
   - Replace Redis broker with pgmq queue topology
   - Add command/event message types
   - Add transactional outbox pattern
   - Reference wiki page for full details

3. Update `infrastructure.md`:
   - Replace container topology (webapp, t3k-sync, audio-worker, video-worker, postgres, nginx)
   - Remove scheduler, redis, monolithic worker
   - Update Docker Compose profile description

4. Update `database.md`:
   - Single database architecture
   - BC-prefixed table naming
   - Table ownership by BC

5. Commit: `docs(skills): update architecture references for event-driven design`

### Task 0.3: Refactor existing wiki pages

**Files:**
- Modify: `../wiki/GTS-Technical-Architecture.md`

**Steps:**

1. Read the following sections of GTS-Technical-Architecture.md:
   - "Database Separation" (~line 1004)
   - "Message Queue (pgmq)" (~line 1066)
   - "Job Scheduling (TaskIQ)" (~line 1178)
   - "Admin API Architecture" (~line 1355)
   - "Containers" subsections

2. Replace each section's content with a brief summary + link to the canonical wiki page:
   ```markdown
   ## Job Scheduling & Messaging

   > **Moved.** See [[Jobs-Architecture-and-Operations]] for the canonical reference
   > on event-driven messaging, container topology, queue architecture, and operations.
   ```

3. Update the Database section to reference single-database architecture.

4. Commit: `docs(wiki): consolidate jobs content to canonical wiki page`

### Task 0.4: Delete superseded plan documents

**Files:**
- Delete: `docs/plans/2026-02-19-bounded-context-architecture.md`
- Delete: `docs/plans/2026-02-19-core-job-dispatch-decoupling.md`
- Delete: `docs/plans/2026-02-19-jobs-wiki-consolidation-plan.md`

**Steps:**

1. Verify each file is fully superseded by the design doc. Read each briefly.
2. `git rm` all three files.
3. Commit: `docs(plans): remove superseded architecture plans`

---

## Phase 0.5: Project Structure Rename

> Rename `libs/` to `model/` and create `infra/messaging/`. This separates
> domain model packages from shared infrastructure. No logic changes.

### Task 0.5.1: Rename libs/ to model/ and update all imports

**Files:**
- Rename: `libs/core/` -> `model/gts/`
- Rename: `libs/audio/` -> `model/audio/`
- Rename: `libs/video/` -> `model/video/`
- Modify: all Python imports referencing `core.`, `audio.`, `video.` from these packages
- Modify: `pyproject.toml` (package paths, import-linter contracts)
- Modify: `docker-compose.yml` (volume mounts)
- Modify: `infrastructure/docker/Dockerfile.dev` (COPY paths)

**Steps:**

1. Rename directories: `libs/core` -> `model/gts`, `libs/audio` -> `model/audio`,
   `libs/video` -> `model/video`.

2. Update all Python imports. The package names inside may stay the same
   (e.g. `from core.records.gear_sync import GearSyncRecord` becomes
   `from gts.records.gear_sync import GearSyncRecord`), or keep the internal
   package name and only change the path. Decide based on what minimises churn.

3. Update `pyproject.toml`:
   - Package discovery paths
   - Import-linter contracts (update source paths)

4. Update Docker volume mounts and Dockerfile COPY commands.

5. Run: `just check`

6. Commit: `refactor(structure): rename libs/ to model/ for domain model clarity`

### Task 0.5.2: Create infra/messaging/ package

**Files:**
- Create: `infra/messaging/src/messaging/__init__.py`
- Create: `infra/messaging/pyproject.toml`

**Steps:**

1. Create the package structure for shared messaging infrastructure.
   This package will hold consumer base classes (Phase 2) and message
   schemas (Phase 2). For now, just the empty package with pyproject.toml.

2. Add import-linter contract: `messaging` can import `sqlalchemy` only.
   It must NOT import any BC domain model (`gts`, `audio`, `video`).

3. Commit: `feat(infra): create messaging package for shared pgmq infrastructure`

---

## Phase 1: Single Database Migration

> Merge `gts_t3k_source` into the main database. Rename all tables with BC
> prefixes. Consolidate to a single Alembic chain. After this phase, the system
> runs on one database with all tables BC-prefixed.

### Task 1.1: Create Alembic migration — rename core tables

**Files:**
- Create: `infrastructure/migrations/versions/0015_rename_core_tables.py`

**Steps:**

1. Generate empty migration:
   ```bash
   just migration "rename core tables with BC prefix"
   ```

2. Write the migration. For each table, use `ALTER TABLE ... RENAME TO`:

   ```python
   from alembic import op

   # fmt: off
   RENAMES = [
       ("users", "core_users"),
       ("oauth_providers", "core_oauth_providers"),
       ("user_identities", "core_user_identities"),
       ("audit_logs", "core_audit_logs"),
       ("user_notifications", "core_user_notifications"),
       ("gear", "core_gear"),
       ("gear_makes", "core_gear_makes"),
       ("gear_models", "core_gear_models"),
       ("gear_sources", "core_gear_sources"),
       ("tags", "core_tags"),
       ("gear_tags", "core_gear_tags"),
       ("user_gear", "core_user_gear"),
       ("signal_chains", "core_signal_chains"),
       ("signal_chain_blocks", "core_signal_chain_blocks"),
       ("signal_chain_groups", "core_signal_chain_groups"),
       ("block_types", "core_block_types"),
       ("presets", "core_presets"),
       ("di_tracks", "core_di_tracks"),
       ("shootouts", "core_shootouts"),
       ("shootout_chains", "core_shootout_chains"),
       ("audio_segments", "core_audio_segments"),
       ("shootout_comments", "core_shootout_comments"),
       ("user_tags", "core_user_tags"),
       ("jobs", "core_jobs"),
   ]
   # fmt: on

   def upgrade() -> None:
       for old, new in RENAMES:
           op.rename_table(old, new)

   def downgrade() -> None:
       for old, new in RENAMES:
           op.rename_table(new, old)
   ```

   Note: `op.rename_table` handles indexes and constraints automatically in PostgreSQL. Foreign keys referencing the old table name are updated by the database engine since they track by OID, not name.

3. Do NOT run the migration yet — ORM models need updating first (Task 1.3).

4. Commit: `feat(db): add migration to rename core tables with BC prefix`

### Task 1.2: Create Alembic migration — add T3K tables to core DB

**Files:**
- Create: `infrastructure/migrations/versions/0016_add_t3k_tables.py`

**Steps:**

1. Generate empty migration (depends on 0015):
   ```bash
   just migration "add T3K staging tables to core DB"
   ```

2. Write the migration to create T3K tables in the core database:

   ```python
   from alembic import op
   import sqlalchemy as sa

   def upgrade() -> None:
       op.create_table(
           "t3k_users_staging",
           sa.Column("id", sa.String(255), primary_key=True),
           sa.Column("username", sa.String(255)),
           sa.Column("avatar_url", sa.String(1024)),
           sa.Column("bio", sa.Text),
           sa.Column("url", sa.String(1024)),
       )
       op.create_table(
           "t3k_tones_staging",
           sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
           sa.Column("title", sa.String(255)),
           sa.Column("description", sa.Text),
           sa.Column("tags", sa.ARRAY(sa.String)),
           sa.Column("makes", sa.ARRAY(sa.String)),
           sa.Column("gear", sa.String(50)),
           sa.Column("platform", sa.String(50)),
           sa.Column("models_count", sa.Integer, server_default="0"),
           sa.Column("favorites_count", sa.Integer, server_default="0"),
           sa.Column("downloads_count", sa.Integer, server_default="0"),
           sa.Column("images", sa.ARRAY(sa.String)),
           sa.Column("user_id", sa.String(255)),
           sa.Column("url", sa.String(1024)),
           sa.Column("created_at", sa.DateTime(timezone=True)),
           sa.Column("updated_at", sa.DateTime(timezone=True)),
           sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
       )
       op.create_table(
           "t3k_models_staging",
           sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
           sa.Column("tone_id", sa.Integer, nullable=False),
           sa.Column("user_id", sa.String(255)),
           sa.Column("name", sa.String(255)),
           sa.Column("model_url", sa.String(1024)),
           sa.Column("size", sa.String(50)),
           sa.Column("created_at", sa.DateTime(timezone=True)),
           sa.Column("updated_at", sa.DateTime(timezone=True)),
           sa.Column("file_synced_at", sa.DateTime(timezone=True), nullable=True),
       )
       op.create_table(
           "t3k_sync_checkpoints",
           sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
           sa.Column("source_name", sa.String(50), nullable=False),
           sa.Column("entity_type", sa.String(50), nullable=False),
           sa.Column("last_synced_at", sa.DateTime(timezone=True)),
           sa.Column("last_record_id", sa.String(255)),
           sa.Column("total_synced", sa.Integer, server_default="0"),
           sa.UniqueConstraint("source_name", "entity_type"),
       )

   def downgrade() -> None:
       op.drop_table("t3k_sync_checkpoints")
       op.drop_table("t3k_models_staging")
       op.drop_table("t3k_tones_staging")
       op.drop_table("t3k_users_staging")
   ```

   Note: The old `sync_checkpoints` table in gts_t3k_source becomes `t3k_sync_checkpoints` in the core DB. Data will be re-synced (no migration of existing T3K staging data needed — sync is idempotent).

3. Commit: `feat(db): add migration to create T3K tables in core DB`

### Task 1.3: Update all webapp ORM `__tablename__` to `core_*` prefix

**Files:**
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user_identity.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear_source.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/gear_model.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user_gear.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/block_type.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/preset.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout_comment.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/tag.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/notification.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/job.py`

**Steps:**

1. For each model file, update `__tablename__` to add `core_` prefix. Example:
   ```python
   # Before
   __tablename__ = "users"
   # After
   __tablename__ = "core_users"
   ```

2. Update the association table in `gear.py`:
   ```python
   # Before
   gear_tags_table = Table("gear_tags", Base.metadata, ...)
   # After
   gear_tags_table = Table("core_gear_tags", Base.metadata, ...)
   ```

3. Update ALL ForeignKey references that use string table names. Search for `ForeignKey("` in each file and update table names. Examples:
   ```python
   # Before
   ForeignKey("gear.id", ondelete="CASCADE")
   # After
   ForeignKey("core_gear.id", ondelete="CASCADE")
   ```

4. Run `just check-types` to verify no type errors.

5. Commit: `refactor(models): rename all core tables with BC prefix`

### Task 1.3b: Update raw SQL table references in scripts and tests

**Files:**
- Modify: `justfile`
- Modify: `scripts/gts_admin.py`
- Modify: `tests/` (integration and E2E tests with raw SQL)

**Steps:**

1. Search all non-migration files for bare table names that will be renamed:
   ```bash
   grep -rn "FROM users\|FROM gear\|FROM jobs\|FROM shootouts\|FROM signal_chains" \
     --include="*.py" --include="*.sql" justfile scripts/ tests/
   ```

2. Update all matches to use `core_*` prefixed names.

3. Search for T3K table references:
   ```bash
   grep -rn "FROM sync_checkpoints\|sync_checkpoints" \
     --include="*.py" --include="*.sql" scripts/ tests/
   ```

4. Update to `t3k_sync_checkpoints`.

5. Run: `just check`

6. Commit: `refactor(scripts): update raw SQL table references for BC prefixes`

### Task 1.4: Move T3K ORM models to use webapp's Base

**Files:**
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/models.py`
- Modify: `infrastructure/migrations/env.py`

**Steps:**

1. Read `sources/t3k/src/source_t3k/adapters/outbound/models.py`.

2. T3K models keep their own `Base` class. Both Bases are registered in
   Alembic so autogenerate can see all tables. Update `infrastructure/migrations/env.py`
   to import both:

   ```python
   # infrastructure/migrations/env.py
   from webapp.adapters.persistence.models.base import Base as WebappBase
   from source_t3k.adapters.outbound.models import Base as T3KBase

   # Combine metadata
   target_metadata = [WebappBase.metadata, T3KBase.metadata]
   ```

3. Update T3K model `__tablename__` values:
   ```python
   # sync_checkpoints → t3k_sync_checkpoints
   class SyncCheckpoint(Base):
       __tablename__ = "t3k_sync_checkpoints"
   ```
   (The other T3K tables already have `t3k_` prefix.)

4. Update `infrastructure/migrations/env.py` to also import T3K models so autogenerate can see them:
   ```python
   # Add to imports
   try:
       from source_t3k.adapters.outbound.models import Base as T3KBase  # noqa: F401
   except ImportError:
       pass
   ```

5. Commit: `refactor(t3k): update table names and Alembic registration`

### Task 1.5: Update init-db.sql — remove gts_t3k_source

**Files:**
- Modify: `infrastructure/docker/init-db.sql`

**Steps:**

1. Remove the `CREATE DATABASE gts_t3k_source` statement.
2. Remove the `GRANT ... gts_t3k_source` statement.
3. Keep the `GRANT ... gts_core` statement.
4. Result should be minimal (gts_core is created by POSTGRES_DB env var):

   ```sql
   -- GTS Database Initialization
   -- Single database architecture: all BCs share gts_core.

   GRANT ALL PRIVILEGES ON DATABASE gts_core TO gts;
   ```

5. Commit: `feat(infra): remove gts_t3k_source from init-db.sql`

### Task 1.5b: Decommission T3K Alembic migration chain

**Files:**
- Modify: `justfile` (remove `migrate-t3k` recipe or T3K alembic calls)
- Modify: `infrastructure/migrations/env.py`
- Archive: `sources/t3k/alembic/` (or delete after verifying tables are in core DB)

**Steps:**

1. Read `justfile` to find all T3K migration commands. Remove or consolidate them.

2. The T3K tables now live in the core DB and are managed by the core Alembic chain.
   Remove the separate T3K Alembic configuration.

3. Verify `just migrate` only runs one Alembic chain.

4. Commit: `chore(db): decommission T3K Alembic migration chain`

### Task 1.6: Update init-pgmq.sql — single database queues

**Files:**
- Modify: `infrastructure/docker/init-pgmq.sql`

**Steps:**

1. Rewrite to operate on gts_core only. Create the NEW queue topology:

   ```sql
   -- pgmq Extension Initialization
   -- All queues in single database (gts_core)

   \c gts_core

   CREATE EXTENSION IF NOT EXISTS pg_partman;
   CREATE EXTENSION IF NOT EXISTS pgmq;

   -- Command queues (point-to-point)
   SELECT pgmq.create('audio_commands');
   SELECT pgmq.create('video_commands');

   -- Event queues (multi-consumer via offset tracking)
   SELECT pgmq.create('audio_events');
   SELECT pgmq.create('video_events');
   SELECT pgmq.create('source_events');

   -- Dead letter queue (shared)
   SELECT pgmq.create('dead_letter');

   -- Legacy queues (kept during transition, removed in Phase 7)
   SELECT pgmq.create('gear_sync');
   SELECT pgmq.create('gear_sync_dlq');

   GRANT ALL ON ALL TABLES IN SCHEMA pgmq TO gts;
   GRANT ALL ON ALL SEQUENCES IN SCHEMA pgmq TO gts;
   GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgmq TO gts;
   ```

   Note: Keep `gear_sync` and `gear_sync_dlq` during transition so the existing consumer still works until Phase 3 replaces it.

2. Commit: `feat(infra): consolidate pgmq queues to single database`

### Task 1.7: Update Docker Compose — remove T3K_DATABASE_URL

**Files:**
- Modify: `docker-compose.yml`

**Steps:**

1. In the `worker` service, remove `T3K_DATABASE_URL` environment variable.
2. In the `scheduler` service, verify no T3K_DATABASE_URL (shouldn't have one).
3. Leave all services pointing to same `DATABASE_URL` (gts_core).

4. Commit: `feat(infra): remove T3K_DATABASE_URL from docker-compose`

### Task 1.8: Update worker db.py — single database sessions

**Files:**
- Modify: `apps/worker/src/worker/db.py`
- Modify: `apps/worker/src/worker/config.py`

**Steps:**

1. Read `apps/worker/src/worker/db.py` and `apps/worker/src/worker/config.py`.

2. In `config.py`: remove `t3k_database_url` from WorkerSettings.

3. In `db.py`:
   - Remove `get_t3k_session()` and `get_t3k_session_no_tx()`.
   - Keep `get_core_session()` and `get_core_session_no_tx()` unchanged.
   - The gear sync consumer will now use `get_core_session()` since T3K tables are in the core DB.

4. Commit: `refactor(worker): remove dual-database session management`

### Task 1.9: Update gear sync consumer — single database

**Files:**
- Modify: `apps/worker/src/worker/consumers/gear_sync.py`
- Modify: `apps/worker/src/worker/entrypoint.py`

**Steps:**

1. Read `apps/worker/src/worker/consumers/gear_sync.py`.

2. The consumer currently takes two sessions (`core_session`, `t3k_session`). Since both are now in the same database, simplify to a single session:
   ```python
   def __init__(
       self,
       session: AsyncSession,  # single session for everything
       pack_queue_name: str,
       ...
   ```

3. Update all `self.t3k_session` references to use `self.session`.
4. Update all `self.core_session` references to use `self.session`.

5. Read `apps/worker/src/worker/entrypoint.py`.

6. Update the consumer subprocess to pass a single session:
   ```python
   async with get_core_session_no_tx() as session:
       consumer = GearSyncConsumer(
           session=session,
           pack_queue_name="gear_sync",
           ...
       )
   ```

7. Run tests: `just tdd tests/integration/worker/test_gear_sync_consumer.py`

8. Commit: `refactor(worker): use single DB session in gear sync consumer`

### Task 1.10: Update T3K publisher — single database

**Files:**
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`

**Steps:**

1. Read the publisher. It uses raw SQL `pgmq.send()` against the T3K database session.
2. No functional change needed — the publisher will receive a session connected to gts_core instead of gts_t3k_source. The SQL is the same.
3. Verify the queue name is still `gear_sync` (it is — this stays until Phase 3 when it becomes `source_events`).
4. Run publisher tests: `just tdd tests/integration/t3k/test_publisher.py`

5. Commit: `test(t3k): verify publisher works with single database`

### Task 1.11: Update import-linter contracts

**Files:**
- Modify: `pyproject.toml`

**Steps:**

1. Read the `[tool.importlinter]` section in pyproject.toml.

2. The contracts need updating because:
   - source_t3k models may now share Base with webapp (if we went that route)
   - Worker no longer needs T3K database URL handling

   If we kept separate Bases (recommended), no import-linter changes are needed for Phase 1. The existing contracts still hold.

3. Verify: `just check-imports` (or equivalent lint command).

4. Commit (if changes needed): `refactor(contracts): update import-linter for single database`

### Task 1.12: Rebuild database and run full test suite

**Steps:**

1. Tear down existing database volumes:
   ```bash
   docker compose down -v
   # Removes containers AND volumes so init scripts rerun on next start
   # User confirmation required — this destroys all data
   ```

2. Rebuild and start services:
   ```bash
   just up-d
   ```

3. Run migrations:
   ```bash
   just migrate
   ```

4. Run full test suite:
   ```bash
   just test-golden-path
   ```

5. Fix any failures.

6. Verify T3K sync still works:
   - Check worker logs: `just logs worker`
   - Verify gear_sync consumer is polling
   - Trigger a manual sync if needed

7. Commit any fixes: `fix(phase1): resolve test failures after DB consolidation`

---

## Phase 2: Command and Event Infrastructure

> Build the messaging primitives: base consumer classes, dataclass message
> schemas, and the consumer offset table. After this phase, the new messaging
> infrastructure exists alongside the old system.

### Task 2.1: Create msg_consumer_offsets table migration

**Files:**
- Create: `infrastructure/migrations/versions/0017_add_consumer_offsets.py`

**Steps:**

1. Generate migration:
   ```bash
   just migration "add msg_consumer_offsets table"
   ```

2. Write migration:
   ```python
   from alembic import op
   import sqlalchemy as sa

   def upgrade() -> None:
       op.create_table(
           "msg_consumer_offsets",
           sa.Column("consumer_id", sa.Text, nullable=False),
           sa.Column("queue_name", sa.Text, nullable=False),
           sa.Column("last_processed_id", sa.BigInteger, nullable=False, server_default="0"),
           sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
           sa.PrimaryKeyConstraint("consumer_id", "queue_name"),
       )

       # Also create pgmq queues via migration for existing environments
       # (init-pgmq.sql only runs on fresh volumes; pgmq.create() is idempotent)
       op.execute("SELECT pgmq.create('audio_commands')")
       op.execute("SELECT pgmq.create('audio_events')")
       op.execute("SELECT pgmq.create('video_commands')")
       op.execute("SELECT pgmq.create('video_events')")
       op.execute("SELECT pgmq.create('source_events')")
       op.execute("SELECT pgmq.create('dead_letter')")

   def downgrade() -> None:
       op.drop_table("msg_consumer_offsets")
   ```

3. Run migration: `just migrate`
4. Commit: `feat(db): add msg_consumer_offsets table for event consumers`

### Task 2.2: Create dataclass message schemas — audio commands

**Files:**
- Create: `infra/messaging/src/messaging/__init__.py`
- Create: `infra/messaging/src/messaging/schemas/base.py`
- Create: `infra/messaging/src/messaging/schemas/audio.py`
- Test: `tests/unit/messaging/test_audio_messages.py`

**Steps:**

1. Write the base message class (dataclasses — `gts-no-frameworks` forbids Pydantic in the domain model, and message schemas live in `infra/messaging` to stay framework-free):
   ```python
   # infra/messaging/src/messaging/schemas/base.py
   from dataclasses import dataclass, field
   from datetime import datetime, timezone

   @dataclass(frozen=True, slots=True)
   class Message:
       type: str
       version: int = 1
       timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

       def to_dict(self) -> dict:
           ...
       @classmethod
       def from_dict(cls, data: dict) -> "Message":
           ...
   ```

2. Write audio command schemas:
   ```python
   # infra/messaging/src/messaging/schemas/audio.py
   @dataclass(frozen=True, slots=True)
   class ProcessChainAudio(Message):
       type: str = "process_chain_audio"
       shootout_id: str = ""
       chain_id: str = ""
       signal_chain_id: str = ""
       di_track_path: str = ""
       # ... additional fields

   @dataclass(frozen=True, slots=True)
   class ProduceMasterTrack(Message):
       type: str = "produce_master_track"
       shootout_id: str = ""
       chain_results: list = field(default_factory=list)

   @dataclass(frozen=True, slots=True)
   class ChainAudioComplete(Message):
       type: str = "chain_audio_complete"
       shootout_id: str = ""
       chain_id: str = ""
       segment_path: str = ""
       duration_seconds: float = 0.0
       integrated_lufs: float = 0.0
       peak_dbfs: float = 0.0

   @dataclass(frozen=True, slots=True)
   class MasterTrackComplete(Message):
       type: str = "master_track_complete"
       shootout_id: str = ""
       master_path: str = ""
       duration_seconds: float = 0.0
       integrated_lufs: float = 0.0
   ```

3. Write unit tests for serialization/deserialization.

4. Run tests: `just tdd tests/unit/messaging/test_audio_messages.py`

5. Commit: `feat(messaging): add audio command and event message schemas`

### Task 2.3: Create dataclass message schemas — video commands

**Files:**
- Create: `infra/messaging/src/messaging/schemas/video.py`
- Test: `tests/unit/messaging/test_video_messages.py`

**Steps:**

1. Write video command/event schemas:
   ```python
   @dataclass(frozen=True, slots=True)
   class ComposeShootout(Message):
       type: str = "compose_shootout"
       job_id: str = ""
       shootout_id: str = ""
       user_id: str = ""
       di_track_path: str = ""
       total_chains: int = 0
       chains: list = field(default_factory=list)

   @dataclass(frozen=True, slots=True)
   class VideoComposeComplete(Message):
       type: str = "video_compose_complete"
       shootout_id: str = ""
       job_id: str = ""
       video_path: str = ""
   ```

2. Write unit tests.
3. Run tests: `just tdd tests/unit/messaging/test_video_messages.py`
4. Commit: `feat(messaging): add video command and event message schemas`

### Task 2.4: Create dataclass message schemas — source events

**Files:**
- Create: `infra/messaging/src/messaging/schemas/source.py`
- Test: `tests/unit/messaging/test_source_messages.py`

**Steps:**

1. The `GearSyncRecord` already exists at `model/gts/src/gts/records/gear_sync.py`. Create a thin source event wrapper that reuses it:
   ```python
   @dataclass(frozen=True, slots=True)
   class GearSynced(Message):
       type: str = "gear_synced"
       source_name: str = ""
       source_record_id: str = ""
       source_updated_at: str = ""
       operation: str = ""
       payload: dict = field(default_factory=dict)
   ```

   Or simply reuse `GearSyncRecord` directly (it already has `to_dict()`/`from_dict()`). Decide based on whether the existing format is sufficient.

2. Write tests.
3. Commit: `feat(messaging): add source event message schemas`

### Task 2.5: Build command consumer base class

**Files:**
- Create: `infra/messaging/src/messaging/__init__.py`
- Create: `infra/messaging/src/messaging/consumers.py`
- Create: `infra/messaging/pyproject.toml`
- Test: `tests/unit/messaging/test_command_consumer.py`

**Steps:**

1. Create `infra/messaging/` — shared infrastructure for pgmq consumer base classes.
   The GTS domain model (`model/gts`) cannot import SQLAlchemy (`gts-no-frameworks`
   contract), so the concrete consumer classes live here. All BC apps (`webapp`,
   `audio_worker`, `video_worker`, `t3k_sync`) depend on `infra/messaging`.

   Add import-linter contract: `messaging` can import `sqlalchemy` only.
   It must NOT import any BC domain model (`gts`, `audio`, `video`).

2. Write the command consumer base:
   ```python
   # infra/messaging/src/messaging/consumers.py
   import asyncio
   import logging
   from collections.abc import Callable, Awaitable
   from sqlalchemy.ext.asyncio import AsyncSession

   logger = logging.getLogger(__name__)

   class CommandConsumer:
       """Base consumer for point-to-point command queues."""

       def __init__(
           self,
           queue_name: str,
           session_factory: Callable[[], AsyncSession],
           handler: Callable[[dict], Awaitable[None]],
           dead_letter_queue: str = "dead_letter",
           max_retries: int = 5,
           visibility_timeout: int = 60,
           batch_size: int = 10,
           poll_interval: float = 1.0,
       ):
           self.queue_name = queue_name
           self.session_factory = session_factory
           self.handler = handler
           self.dead_letter_queue = dead_letter_queue
           self.max_retries = max_retries
           self.vt = visibility_timeout
           self.qty = batch_size
           self.poll_interval = poll_interval

       async def run(self) -> None:
           """Infinite polling loop."""
           logger.info("Starting command consumer for %s", self.queue_name)
           while True:
               try:
                   await self._poll_and_process()
               except Exception:
                   logger.exception("Error in consumer loop for %s", self.queue_name)
                   await asyncio.sleep(5)
               await asyncio.sleep(self.poll_interval)

       async def _poll_and_process(self) -> None:
           async with self.session_factory() as session:
               result = await session.execute(
                   sa.text("SELECT * FROM pgmq.read_with_poll(:queue, :vt, :qty)"),
                   {"queue": self.queue_name, "vt": self.vt, "qty": self.qty},
               )
               messages = result.fetchall()

               for msg in messages:
                   msg_id = msg.msg_id
                   read_ct = msg.read_ct
                   payload = msg.message

                   if read_ct > self.max_retries:
                       await self._dead_letter(session, msg)
                       continue

                   try:
                       await self.handler(payload)
                       await session.execute(
                           sa.text("SELECT pgmq.archive(:queue, :msg_id)"),
                           {"queue": self.queue_name, "msg_id": msg_id},
                       )
                       await session.commit()
                   except Exception:
                       logger.exception("Failed processing message %s", msg_id)
                       await session.rollback()
   ```

3. Write tests using real PostgreSQL + pgmq.
4. Run tests.
5. Commit: `feat(messaging): add command consumer base class`

### Task 2.6: Build event consumer base class

**Files:**
- Modify: `infra/messaging/src/messaging/consumers.py`
- Test: `tests/unit/messaging/test_event_consumer.py`

**Steps:**

1. Add an event consumer that uses offset tracking:

   ```python
   class EventConsumer:
       """Base consumer for multi-consumer event queues using offset tracking."""

       def __init__(
           self,
           consumer_id: str,
           queue_name: str,
           session_factory: Callable,
           handler: Callable[[dict], Awaitable[None]],
           poll_interval: float = 1.0,
       ):
           self.consumer_id = consumer_id
           self.queue_name = queue_name
           self.session_factory = session_factory
           self.handler = handler
           self.poll_interval = poll_interval

       async def run(self) -> None:
           logger.info("Starting event consumer %s for %s", self.consumer_id, self.queue_name)
           while True:
               try:
                   await self._poll_and_process()
               except Exception:
                   logger.exception("Error in event consumer %s", self.consumer_id)
                   await asyncio.sleep(5)
               await asyncio.sleep(self.poll_interval)

       async def _poll_and_process(self) -> None:
           async with self.session_factory() as session:
               # Get current offset
               result = await session.execute(
                   sa.text("""
                       SELECT last_processed_id FROM msg_consumer_offsets
                       WHERE consumer_id = :cid AND queue_name = :queue
                       FOR UPDATE
                   """),
                   {"cid": self.consumer_id, "queue": self.queue_name},
               )
               row = result.fetchone()
               last_id = row.last_processed_id if row else 0

               # Read messages after offset from pgmq queue table
               # Table name is a controlled internal value, safe for f-string
               queue_table = f"pgmq.q_{self.queue_name}"
               result = await session.execute(
                   sa.text(f"""
                       SELECT msg_id, message FROM {queue_table}
                       WHERE msg_id > :last_id
                       ORDER BY msg_id
                       LIMIT 10
                   """),
                   {"last_id": last_id},
               )
               messages = result.fetchall()

               for msg in messages:
                   await self.handler(msg.message)
                   # Advance offset
                   await session.execute(
                       sa.text("""
                           INSERT INTO msg_consumer_offsets (consumer_id, queue_name, last_processed_id, updated_at)
                           VALUES (:cid, :queue, :msg_id, now())
                           ON CONFLICT (consumer_id, queue_name)
                           DO UPDATE SET last_processed_id = :msg_id, updated_at = now()
                       """),
                       {"cid": self.consumer_id, "queue": self.queue_name, "msg_id": msg.msg_id},
                   )
                   await session.commit()
   ```

   Note: The exact SQL for reading from the pgmq queue table directly (rather than `pgmq.read()`) needs prototyping. The pgmq queue table is named `pgmq.q_{queue_name}`. Direct SELECT from this table avoids visibility timeout semantics (which are for point-to-point, not broadcast). This is the key Phase 2 prototype mentioned in the design doc.

2. Write integration tests with real pgmq.
3. Run tests.
4. Commit: `feat(messaging): add event consumer base class with offset tracking`

### Task 2.7: Integration test — full command/event round-trip

**Files:**
- Create: `tests/integration/worker/test_messaging_roundtrip.py`

**Steps:**

1. Write a test that:
   - Sends a command to `audio_commands` via `pgmq.send()`
   - Runs the command consumer for one iteration
   - Verifies the handler was called with correct payload
   - Verifies the message was archived

2. Write a test that:
   - Sends an event to `audio_events` via `pgmq.send()`
   - Runs the event consumer for one iteration
   - Verifies the handler was called
   - Verifies the consumer offset was advanced

3. Run: `just tdd tests/integration/worker/test_messaging_roundtrip.py`

4. Commit: `test(worker): add messaging round-trip integration tests`

---

## Phase 3: T3K Sync Container

> Extract the T3K sync into its own container. The sync becomes a self-driven
> eternal loop publishing to `source_events`. The scheduler container is removed.

### Task 3.1: Create t3k-sync entry point

**Files:**
- Create: `apps/t3k_sync/__init__.py`
- Create: `apps/t3k_sync/src/t3k_sync/__init__.py`
- Create: `apps/t3k_sync/src/t3k_sync/main.py`
- Create: `apps/t3k_sync/src/t3k_sync/config.py`
- Create: `apps/t3k_sync/pyproject.toml`

**Steps:**

1. Create the package structure following existing app patterns (copy from `apps/worker/`).

2. Write `config.py`:
   ```python
   from pydantic_settings import BaseSettings

   class T3KSyncSettings(BaseSettings):
       database_url: str = "postgresql+asyncpg://gts:gts_dev_password@db:5432/gts_core"
       oauth_encryption_key: str = ""
       gts_storage_root: str = "/app/storage"
       poll_interval_seconds: int = 60
       token_refresh_buffer_seconds: int = 600

       model_config = {"env_prefix": ""}
   ```

3. Write `main.py`:
   ```python
   import asyncio
   import logging
   from t3k_sync.config import T3KSyncSettings
   from source_t3k.services.sync_service import T3KSyncService
   from source_t3k.adapters.outbound.publisher import GearSyncPublisher
   from source_t3k.adapters.inbound.token_manager import T3KTokenManager

   logger = logging.getLogger(__name__)

   async def run_sync_loop() -> None:
       settings = T3KSyncSettings()
       # ... initialise token manager, sync service, publisher
       # Ensure valid token at startup
       # Enter eternal loop:
       while True:
           try:
               async with get_session() as session:
                   publisher = GearSyncPublisher(session, queue_name="source_events")
                   result = await sync_service.run_sync_batch(publisher)
                   logger.info("Sync batch: %s", result)
           except Exception:
               logger.exception("Sync batch failed")
           await asyncio.sleep(settings.poll_interval_seconds)

   def main():
       asyncio.run(run_sync_loop())
   ```

4. Write `pyproject.toml` with dependencies on `source_t3k`, `gts`.

5. Add import-linter contract for `t3k_sync`: can only import `source_t3k`, `gts`, `messaging`.

6. Commit: `feat(t3k-sync): create standalone sync container entry point`

### Task 3.2: Add t3k-sync service to Docker Compose

**Files:**
- Modify: `docker-compose.yml`

**Steps:**

1. Add `t3k-sync` service under the `jobs` profile:

   ```yaml
   t3k-sync:
     profiles:
       - jobs
     build:
       context: .
       dockerfile: infrastructure/docker/Dockerfile.dev
       args:
         UID: ${UID:-1000}
         GID: ${GID:-1000}
     command: python -m t3k_sync.main
     environment:
       DATABASE_URL: postgresql+asyncpg://gts:${DB_PASSWORD:-gts_dev_password}@db:5432/gts_core
       ENV: ${ENV:-development}
       OAUTH_ENCRYPTION_KEY: ${OAUTH_ENCRYPTION_KEY}
       GTS_STORAGE_ROOT: /app/storage
       GTS_AUTH_FILE: /worktrees/.gts-auth.json
     volumes:
       - ./model:/app/model:ro
       - ./infra:/app/infra:ro
       - ./sources:/app/sources:ro
       - ./apps/t3k_sync:/app/apps/t3k_sync
       - ../gts-storage:/app/storage
       - ../:/worktrees:ro
     depends_on:
       db:
         condition: service_healthy
     restart: unless-stopped
   ```

   Note: All BC containers share `Dockerfile.dev` and broad volume mounts in
   development. This is pragmatic for dev -- import-linter enforces BC isolation
   at the code level. Production builds would use per-BC images with restricted
   COPY sets.

2. Commit: `feat(infra): add t3k-sync container to docker-compose`

### Task 3.3: Update T3K publisher to use source_events queue

**Files:**
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`

**Steps:**

1. Change the default queue name from `gear_sync` to `source_events`.
2. Update any hardcoded queue name references.
3. **Critical:** Ensure the `pgmq.send('source_events', ...)` call happens within
   the same database transaction as the T3K staging table writes. The current code
   publishes after commit — this must be fixed to use the transactional outbox pattern.
4. Update tests.
5. Run tests: `just tdd tests/integration/t3k/`
6. Commit: `refactor(t3k): publish to source_events queue`

### Task 3.4: Create source_events consumer in webapp

**Files:**
- Create: `apps/webapp/src/webapp/consumers/__init__.py`
- Create: `apps/webapp/src/webapp/consumers/source_events.py`

**Steps:**

1. Create a consumer that reads `source_events` using the `EventConsumer` base class from `infra/messaging` and processes gear sync records — essentially extracting the GearMapperService logic that currently lives in the worker's GearSyncConsumer.

2. The consumer_id should be `"webapp:source_events"`.

3. Wire this consumer into the webapp startup (run as a background task in the FastAPI lifespan).

4. Test: verify gear data flows from T3K sync → source_events → webapp consumer → core tables.

5. Commit: `feat(webapp): add source_events consumer for gear mapping`

### Task 3.5: Remove scheduler container

**Files:**
- Modify: `docker-compose.yml` (remove scheduler service)
- Delete: `apps/scheduler/` (entire directory — after extracting any reusable logic)

**Steps:**

1. Read the scheduler's 5 tasks to determine what must be preserved:
   - `monitor_stale_jobs` → Move to webapp background task
   - `process_pending_retries` → Move to webapp background task
   - `dispatch_pending_jobs` → Eliminated (pgmq replaces HTTP dispatch)
   - `scheduler_heartbeat` → Eliminated (no distributed lock needed)
   - `ensure_source_sync_running` → Eliminated (t3k-sync is self-driven)

2. Create `apps/webapp/src/webapp/background_tasks.py` with the two preserved tasks as periodic asyncio tasks running in the webapp lifespan.

3. Remove `JobType.SOURCE_SYNC` from all code paths:
   - `apps/webapp/src/webapp/api/v1/jobs.py` — remove SOURCE_SYNC handling
   - `apps/worker/src/worker/admin.py` — remove SOURCE_SYNC dispatch/trigger
   - Core JobType enum — remove SOURCE_SYNC variant
   - Update any tests referencing SOURCE_SYNC

4. Remove scheduler from docker-compose.yml.
5. Delete `apps/scheduler/` directory.
6. Update import-linter contracts (remove scheduler from root packages).
7. Run: `just test-golden-path`

8. Commit: `feat(webapp): move job monitoring to webapp background tasks`
9. Commit: `chore(scheduler): remove scheduler container`

### Task 3.6: Remove gear_sync consumer from worker

**Files:**
- Modify: `apps/worker/src/worker/entrypoint.py`

**Steps:**

1. Remove the pgmq consumer subprocess from the worker entrypoint. The gear sync consumer's role is now handled by the webapp's source_events consumer (Task 3.4).

2. The worker now runs only: admin API + TaskIQ worker (temporarily, until Phases 4-5 replace them).

3. Run: `just test-golden-path`

4. Commit: `refactor(worker): remove gear sync consumer from worker`

---

## Phase 4: Audio BC Container

> Extract audio processing into its own container. The audio-worker consumes
> `audio_commands` and publishes `audio_events`.

### Task 4.1: Create audio-worker entry point

**Files:**
- Create: `apps/audio_worker/__init__.py`
- Create: `apps/audio_worker/src/audio_worker/__init__.py`
- Create: `apps/audio_worker/src/audio_worker/main.py`
- Create: `apps/audio_worker/src/audio_worker/config.py`
- Create: `apps/audio_worker/src/audio_worker/handlers.py`
- Create: `apps/audio_worker/pyproject.toml`

**Steps:**

1. Create the package structure.

2. Write `handlers.py` — extract audio processing logic from existing TaskIQ handlers:
   - `handle_shootout_audio_job.kiq()` → `handle_process_chain_audio(message)` consuming from `audio_commands`
   - `handle_shootout_master_job.kiq()` → `handle_produce_master_track(message)` consuming from `audio_commands`
   - `handle_audio_processing.kiq()` → `handle_process_audio_file(message)` consuming from `audio_commands`

   Each handler:
   - Receives a thick message (no job_id lookups needed for input data)
   - Processes audio
   - Publishes result to `audio_events` (transactional outbox)
   - Does NOT touch `core_jobs` — webapp event consumers handle status updates

3. Write `main.py`:
   ```python
   async def run():
       consumer = CommandConsumer(
           queue_name="audio_commands",
           session_factory=get_core_session,
           handler=dispatch_audio_command,
       )
       await consumer.run()
   ```

4. Route commands by `type` field:
   ```python
   async def dispatch_audio_command(payload: dict) -> None:
       msg_type = payload["type"]
       if msg_type == "process_chain_audio":
           await handle_process_chain_audio(payload)
       elif msg_type == "produce_master_track":
           await handle_produce_master_track(payload)
       elif msg_type == "process_audio_file":
           await handle_process_audio_file(payload)
       else:
           raise ValueError(f"Unknown audio command: {msg_type}")
   ```

5. Add import-linter contract for `audio_worker`: can only import `gts`, `messaging`.

6. Commit: `feat(audio-worker): create audio BC container with command consumer`

### Task 4.2: Add audio-worker to Docker Compose

**Files:**
- Modify: `docker-compose.yml`

**Steps:**

1. Add `audio-worker` service under `jobs` profile:
   ```yaml
   audio-worker:
     profiles:
       - jobs
     build:
       context: .
       dockerfile: infrastructure/docker/Dockerfile.dev
     command: python -m audio_worker.main
     environment:
       DATABASE_URL: postgresql+asyncpg://gts:${DB_PASSWORD:-gts_dev_password}@db:5432/gts_core
       GTS_STORAGE_ROOT: /app/storage
     volumes:
       - ./model:/app/model:ro
       - ./infra:/app/infra:ro
       - ./apps/audio_worker:/app/apps/audio_worker
       - ../gts-storage:/app/storage
     depends_on:
       db:
         condition: service_healthy
     restart: unless-stopped
   ```

2. Commit: `feat(infra): add audio-worker container to docker-compose`

### Task 4.3: Integration test — audio command processing

**Files:**
- Create: `tests/integration/audio_worker/test_audio_commands.py`

**Steps:**

1. Write tests that:
   - Send a `process_chain_audio` command to `audio_commands` queue
   - Run the audio worker for one message
   - Verify audio processing completed
   - Verify `chain_audio_complete` event published to `audio_events`
   - Verify audio worker does NOT touch `core_jobs` (BC isolation)

2. Run: `just tdd tests/integration/audio_worker/`

3. Commit: `test(audio-worker): add integration tests for audio commands`

---

## Phase 5: Video BC Container

> Refactor the video service into a consumer-based container. The video-worker
> consumes `video_commands` and `audio_events`, publishes `video_events` and
> `audio_commands`.

### Task 5.1: Refactor video service to consumer model

**Files:**
- Modify: `model/video/` (existing video library)
- Create: `apps/video_worker/src/video_worker/main.py`
- Create: `apps/video_worker/src/video_worker/handlers.py`
- Create: `apps/video_worker/src/video_worker/reconciliation.py`

**Steps:**

1. The current `video` container runs as an HTTP API (`Dockerfile.video`, uvicorn on 8002). Refactor to a consumer-based architecture:

   - Consume `video_commands` for new compose requests
   - Consume `audio_events` (offset-based) to track chain completion
   - Publish `audio_commands` to request audio processing
   - Publish `video_events` on completion

2. Write `reconciliation.py` — tracks which chains are complete for each shootout:
   ```python
   class ShootoutReconciler:
       """Tracks audio chain completion for active shootouts.

       Uses total_chains from the compose_shootout command — never queries
       core_* tables. Video BC has zero access to Core BC tables.
       """

       async def on_compose_shootout(self, command: dict) -> None:
           """Register a new shootout with its expected chain count."""
           # Store shootout_id -> total_chains locally (in-memory dict or video-owned table)
           ...

       async def on_chain_audio_complete(self, event: dict) -> str | None:
           """Returns shootout_id if all chains complete, else None."""
           # Increment completed count, compare against stored total_chains
           ...

       async def on_master_track_complete(self, event: dict) -> str:
           """Returns shootout_id — master is ready, proceed to video render."""
           ...
   ```

3. Write `handlers.py`:
   - `handle_compose_shootout(message)`: Creates sub-jobs, dispatches `process_chain_audio` commands
   - `handle_audio_event(event)`: Routes to reconciler, triggers next steps

4. Wire into `main.py` with two consumer loops (command + event).

5. Update `Dockerfile.video` CMD to run consumer instead of uvicorn.

6. Commit: `feat(video-worker): refactor to consumer-based architecture`

### Task 5.2: Update Docker Compose for video-worker

**Files:**
- Modify: `docker-compose.yml`

**Steps:**

1. Rename the `video` service to `video-worker`.
2. Update command from uvicorn to consumer entry point.
3. Add necessary environment variables.
4. Remove port exposure (no HTTP API needed).
5. Commit: `feat(infra): update video service to consumer-based video-worker`

### Task 5.3: Integration test — video compose workflow

**Files:**
- Create: `tests/integration/video_worker/test_compose_workflow.py`

**Steps:**

1. Write end-to-end test for the shootout flow:
   - Send `compose_shootout` to `video_commands`
   - Verify `process_chain_audio` commands published to `audio_commands`
   - Simulate `chain_audio_complete` events on `audio_events`
   - Verify reconciliation triggers `produce_master_track`
   - Simulate `master_track_complete` event
   - Verify video rendering triggered
   - Verify `video_compose_complete` published to `video_events`

2. Run: `just tdd tests/integration/video_worker/`

3. Commit: `test(video-worker): add compose workflow integration tests`

---

## Phase 6: Webapp Decoupling

> Replace HTTP dispatch with direct pgmq command publishing. The webapp becomes
> a pure command producer and event consumer.

### Task 6.1: Replace enqueue_to_worker with pgmq publish

**Files:**
- Modify: `apps/webapp/src/webapp/services/processing_service.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/v1/jobs.py`

**Steps:**

1. Read `apps/webapp/src/webapp/services/processing_service.py`.

2. Replace `enqueue_to_worker()` with a function that publishes to pgmq:
   ```python
   async def dispatch_job(session: AsyncSession, job: Job) -> None:
       """Publish job command to appropriate pgmq queue (transactional outbox)."""
       if job.job_type == JobType.VIDEO_COMPOSE:
           command = build_compose_shootout_command(job)
           await session.execute(
               sa.text("SELECT pgmq.send(:queue, CAST(:msg AS jsonb))"),
               {"queue": "video_commands", "msg": json.dumps(command.to_dict())},
           )
       elif job.job_type in (JobType.AUDIO_PROCESSING, JobType.SHOOTOUT_AUDIO):
           command = build_audio_command(job)
           await session.execute(
               sa.text("SELECT pgmq.send(:queue, CAST(:msg AS jsonb))"),
               {"queue": "audio_commands", "msg": json.dumps(command.to_dict())},
           )
   ```

   **Critical:** The pgmq.send() call MUST be in the same transaction as the Job INSERT. This is the transactional outbox pattern.

3. Update all call sites in shootouts.py and jobs.py to use the new function.

4. Remove the old `enqueue_to_worker()` function and its httpx dependency.

5. Run: `just tdd tests/integration/webapp/`

6. Commit: `feat(webapp): replace HTTP dispatch with pgmq transactional outbox`

### Task 6.2: Add event consumers to webapp

**Files:**
- Create: `apps/webapp/src/webapp/consumers/video_events.py`
- Create: `apps/webapp/src/webapp/consumers/audio_events.py`

**Steps:**

1. Add `video_events` consumer:
   - Consumer ID: `"webapp:video_events"`
   - On `video_compose_complete`: update `core_jobs` status to COMPLETED, update shootout video path

2. Add `audio_events` consumer:
   - Consumer ID: `"webapp:audio_events"`
   - On `audio_file_complete`: update `core_jobs` status to COMPLETED
   - On `chain_audio_complete`: update job progress percentage

3. Wire into webapp lifespan as background tasks.

4. Run: `just test-golden-path`

5. Commit: `feat(webapp): add video and audio event consumers`

### Task 6.3: Remove worker admin enqueue endpoint

**Files:**
- Modify: `apps/worker/src/worker/admin.py`

**Steps:**

1. Remove the `/api/admin/enqueue` endpoint.
2. Remove all `.kiq()` calls from admin.py.
3. Remove TaskIQ imports from admin.py.
4. Keep the admin endpoints that are still useful (job listing, health check) — these will move to webapp later.

5. Run: `just tdd tests/integration/worker/`

6. Commit: `refactor(worker): remove enqueue endpoint and TaskIQ dispatch`

---

## Phase 7: Cleanup and Removal

> Remove all deprecated infrastructure: TaskIQ, Redis, monolithic worker,
> remaining legacy code.

### Task 7.1: Remove TaskIQ dependency

**Files:**
- Modify: `apps/worker/src/worker/main.py` (remove broker creation)
- Modify: `apps/worker/src/worker/entrypoint.py` (remove TaskIQ subprocess)
- Delete: `apps/worker/src/worker/jobs/shootout.py`
- Delete: `apps/worker/src/worker/jobs/audio.py`
- Delete: `apps/worker/src/worker/jobs/master_audio.py`
- Delete: `apps/worker/src/worker/jobs/source_sync.py`
- Delete: `apps/worker/src/worker/jobs/audio_processing.py`
- Modify: `pyproject.toml` (remove taskiq, taskiq-redis dependencies)

**Steps:**

1. Delete all TaskIQ job handler files.
2. Remove TaskIQ broker creation from worker main.py.
3. Remove TaskIQ worker subprocess from entrypoint.py.
4. Remove `taskiq` and `taskiq-redis` from dependencies.
5. Run: `just check`

6. Commit: `chore(worker): remove TaskIQ dependency entirely`

### Task 7.2: Remove Redis from infrastructure

**Files:**
- Modify: `docker-compose.yml` (remove redis service)
- Modify: `apps/worker/src/worker/config.py` (remove redis_url)
- Delete: `apps/scheduler/src/scheduler/lock.py` (if not already deleted)
- Modify: `infrastructure/docker/init-pgmq.sql` (remove legacy queues)

**Steps:**

1. Remove `redis` service from docker-compose.yml.
2. Remove `redis_data` from volumes section.
3. Remove `REDIS_URL` from all service environment sections.
4. Remove all Redis imports and usage from remaining code.
5. Remove worker dependency on redis service.
6. Remove legacy queues (`gear_sync`, `gear_sync_dlq`) from init-pgmq.sql.
7. Run: `just check`

8. Commit: `chore(infra): remove Redis and legacy queues`

### Task 7.3: Remove monolithic worker container

**Files:**
- Modify: `docker-compose.yml` (remove worker service)
- Archive or delete: `apps/worker/` (entire directory)

**Steps:**

1. At this point, the worker's responsibilities have been distributed:
   - Audio processing → `audio-worker` container
   - Video processing → `video-worker` container
   - T3K sync → `t3k-sync` container
   - Gear mapping → `webapp` consumer
   - Job monitoring → `webapp` background tasks
   - Admin API → `webapp` admin routes

2. Move any remaining admin endpoints to webapp.
3. Remove `worker` service from docker-compose.yml.
4. Delete or archive `apps/worker/`.
5. Update import-linter contracts (remove worker from root packages).
6. Run: `just test-golden-path`

7. Commit: `chore(worker): remove monolithic worker container`

### Task 7.4: Clean up Docker Compose and worktree.py

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.ci.yml`
- Modify: `worktree/docker.py`
- Modify: `worktree/templates.py`

**Steps:**

1. Update docker-compose.yml:
   - Verify `--profile jobs` services are: `t3k-sync`, `audio-worker`, `video-worker`
   - Remove references to scheduler, redis
   - Update service dependency graph

2. Update docker-compose.ci.yml for new service topology.

3. Update worktree.py:
   - Remove Redis port allocation
   - Remove scheduler references
   - Update service health checks for new containers
   - Update `start_services()` for new topology

4. Run: `just up-d && just test-golden-path`

5. Commit: `chore(infra): clean up Docker Compose for event-driven topology`

6. Add import-linter contracts for each new BC package:
   - `t3k_sync` — can only import `source_t3k`, `gts`, `messaging` (no webapp, no audio, no video)
   - `audio_worker` — can only import `gts`, `messaging` (no webapp, no video, no source_t3k)
   - `video_worker` — can only import `gts`, `messaging` (no webapp, no audio, no source_t3k)

7. Commit: `refactor(contracts): add import-linter contracts for new BC packages`

### Task 7.4b: Implement event queue janitor

**Files:**
- Modify: `apps/webapp/src/webapp/background_tasks.py`

**Steps:**

1. Add a periodic background task that archives old event messages:
   - For each event queue (`audio_events`, `video_events`, `source_events`):
     - Query `msg_consumer_offsets` for the minimum `last_processed_id` across
       all registered consumers for that queue.
     - Archive all messages in the pgmq queue table with `msg_id` below that minimum.
   - Run on a configurable interval (default: hourly).

2. Write integration test verifying cleanup works correctly.

3. Commit: `feat(webapp): add event queue janitor background task`

### Task 7.5: Final documentation update

**Files:**
- Modify: `AGENTS.md`
- Modify: `../wiki/Jobs-Architecture-and-Operations.md`
- Modify: `DEVELOPMENT.md`

**Steps:**

1. Update AGENTS.md to remove all references to:
   - TaskIQ
   - Redis
   - Scheduler container
   - Monolithic worker
   - `enqueue_to_worker()`
   - `.kiq()` calls

2. Update wiki page to change tense from "will be" to "is" for implemented features.

3. Update DEVELOPMENT.md with new container topology and commands.

4. Run: `just check`

5. Commit: `docs: finalise documentation for event-driven architecture`

---

## Phase Summary

| Phase | Tasks | Key Deliverable |
|-------|-------|----------------|
| 0 | 4 | Documentation updated for target architecture |
| 0.5 | 2 | Project structure: libs/ -> model/, new infra/messaging/ |
| 1 | 14 | Single database, BC-prefixed tables, system working |
| 2 | 7 | Message schemas, consumer base classes, offset tracking |
| 3 | 6 | T3K sync in own container, scheduler removed, SOURCE_SYNC eliminated |
| 4 | 3 | Audio processing in own container |
| 5 | 3 | Video processing in own container |
| 6 | 3 | Webapp dispatches via pgmq, HTTP dispatch removed |
| 7 | 6 | TaskIQ, Redis, monolithic worker removed, event janitor |
| **Total** | **48** | **Event-driven architecture fully operational** |

## Risk Notes

1. **Phase 1 is the riskiest.** Table renames touch every query. Run full test suite after each change.
2. **Phase 2 event consumer** offset-based pattern needs prototyping. Direct pgmq table reads may need adjustment.
3. **Phase 3-5 can be parallelised** if different developers work on each BC extraction.
4. **Phase 6 is the integration point.** Test end-to-end flows thoroughly.
5. **Database volumes must be recreated** after Phase 1 (init-db.sql changes).
