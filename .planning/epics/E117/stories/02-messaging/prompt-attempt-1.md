[GTS]|rules:{authentication,github,testing-database}|skills:{gts-architecture,gts-backend-dev,gts-testing}|wiki:{api-design,design-patterns,testing}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 02-messaging
**Name:** Messaging Infrastructure
**Purpose:** Create pgmq wrapper, message envelope schema, command/event types, consumer base class, and transactional outbox. This provides the messaging foundation all BC containers use.

### Scope
**Create:**
- `libs/core/src/core/records/envelope.py`
- `libs/core/src/core/records/commands.py`
- `libs/core/src/core/records/events.py`
- `libs/core/src/core/ports/message_bus.py`
- `libs/core/src/core/services/pgmq_client.py`
- `libs/core/src/core/services/consumer_base.py`
- `tests/unit/core/test_messaging.py`
**Modify:**
- `pyproject.toml`
- `libs/core/pyproject.toml`
- `libs/core/src/core/records/__init__.py`
- `libs/core/src/core/ports/__init__.py`
- `libs/core/src/core/services/__init__.py`

### Implementation Notes
- The design doc specifies infra/messaging/ as a separate workspace member. For this implementation, messaging infrastructure lives in libs/core alongside existing ports and records, since all BCs already depend on core. A future extraction to a separate package can happen if needed.
- libs/core/src/core/records/envelope.py — MessageEnvelope Pydantic model with message_id (UUIDv7), message_type, source_bc, timestamp, correlation_id, payload dict
- libs/core/src/core/records/commands.py — Command schemas: ProcessAudioCommand, RenderVideoCommand, SyncGearCommand. Each extends MessageEnvelope with typed payload.
- libs/core/src/core/records/events.py — Event schemas: GearSyncedEvent, AudioProcessedEvent, VideoRenderedEvent
- libs/core/src/core/ports/message_bus.py — Protocol for pgmq operations: send, read, archive, create_queue, drop_queue
- libs/core/src/core/services/pgmq_client.py — Async pgmq wrapper implementing MessageBus protocol. Uses raw SQL via SQLAlchemy for pgmq.send(), pgmq.read_with_poll(), pgmq.archive(), pgmq.create(). Handles visibility timeout and batch reads.
- libs/core/src/core/services/consumer_base.py — Abstract consumer base class with: async poll loop, visibility timeout handling, retry with exponential backoff, DLQ routing when read_ct exceeds max retries, graceful shutdown via signal handlers
- Add pgmq queue creation to init-core-db.sh — create queues: gear_sync, process_audio, render_video, and their DLQ counterparts
- Add asyncpg or psycopg as dependency to libs/core/pyproject.toml for raw pgmq SQL operations
- Update pyproject.toml workspace config and import-linter contracts for new modules
- Write tests/unit/core/test_messaging.py — test envelope serialisation, command/event schema validation, consumer retry logic

### Validation Checkpoint

After this story, a **process** validation will verify:
- Messaging unit tests pass — envelope serialisation, command/event schemas, consumer logic (evidence: command, exit_code, output_tail)
