# Context: E94 — Phase 5A/5B/5C

## What Already Exists

| Component | Status | Location |
|-----------|--------|----------|
| Job entity (full state machine) | Complete | `libs/core/src/core/domain/entities/job.py` |
| JobStatus/JobType enums | Complete | `libs/core/src/core/domain/value_objects/job_status.py` |
| Job ORM model + migration | Complete | `apps/webapp/.../models/job.py` |
| Job repository | Complete | `apps/webapp/.../repositories/job_repository.py` |
| Job service + API endpoints | Complete | `apps/webapp/src/webapp/services/job_service.py`, `.../api/v1/jobs.py` |
| GearSyncRecord contract | Complete | `libs/core/src/core/records/gear_sync.py` |
| Audio ChainExecutor | Complete | `libs/audio/src/audio/processing/chain_executor.py` |
| Loudness (EBU R128) | Complete | `libs/audio/src/audio/processing/loudness.py` |
| NAM/IR loaders | Complete | `libs/audio/src/audio/processing/` |
| Waveform extraction | Complete | `libs/audio/src/audio/analysis/waveform.py` |
| Shootout entity + ORM + repo + service + API | Complete | `libs/core/.../shootout.py`, `apps/webapp/...` |
| AudioSegment ORM model | Complete | `apps/webapp/.../models/shootout.py` |
| ShootoutStatus enum (DRAFT→PENDING→RUNNING→PROCESSING→COMPLETED→FAILED) | Complete | `apps/webapp/.../models/shootout.py` |
| SignalChain entity + ORM + repo | Complete | `libs/core/.../signal_chain.py`, `apps/webapp/...` |
| DITrack entity + ORM | Complete | `libs/core/.../di_track.py`, `apps/webapp/.../models/shootout.py` |
| Docker services (worker, scheduler, redis) | Complete | `docker-compose.yml` (profile: jobs) |
| pgmq queues (init-pgmq.sql) | Complete | `infrastructure/docker/init-pgmq.sql` |
| Worker scaffold (InMemoryBroker) | Scaffold | `apps/worker/src/worker/main.py` |
| Scheduler scaffold (InMemoryBroker) | Scaffold | `apps/scheduler/src/scheduler/main.py` |
| T3K source adapter (empty dirs) | Scaffold | `sources/t3k/src/source_t3k/` |

## Key Patterns

- **Worker pyproject.toml** depends on: gts-core, gts-audio, taskiq, taskiq-redis, sqlalchemy, asyncpg, pgmq-sqlalchemy, redis, pydantic, httpx
- **Scheduler pyproject.toml** depends on: gts-core, taskiq, taskiq-redis, redis, pydantic
- **T3K pyproject.toml** depends on: gts-core, httpx, sqlalchemy, asyncpg, pgmq-sqlalchemy, pydantic
- **All relationships** use `lazy="raise"` — must use `joinedload()` in queries
- **Admin API** has NO auth — port 8001 not exposed publicly
- **Webapp → Worker** communication via HTTP POST to Admin API
- **Docker command** for worker: `taskiq worker worker.main:broker --workers 1`
- **Docker command** for scheduler: `taskiq scheduler scheduler.main:scheduler`
- **JobType enum** currently: AUDIO_PROCESSING, VIDEO_COMPOSITION, GEAR_SYNC, MODEL_DOWNLOAD, IR_DOWNLOAD, NOTIFICATION
- **pgmq queues** in gts_t3k_source: gear_pack_sync, gear_model_sync, preset_sync, sync_dead_letter
- **pgmq queues** in gts_core: audio_processing, video_composition, notifications, jobs_dead_letter
