[GTS]|rules:{authentication,container-execution,github}|skills:{docker-infra,gts-architecture,gts-backend-dev}|wiki:{api-design,design-patterns,infrastructure}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 03-containers
**Name:** Per-BC Containers
**Purpose:** Create t3k-sync, audio-worker, and video-worker containers. Move sync logic from monolithic worker and scheduler into t3k-sync. Move audio and video processing into their respective workers. Remove the scheduler app.

### Scope
**Create:**
- `infrastructure/docker/Dockerfile.t3k-sync`
- `infrastructure/docker/Dockerfile.audio-worker`
**Modify:**
- `docker-compose.yml`
- `docker-compose.override.yml`
- `pyproject.toml`
- `apps/worker/src/worker/main.py`
- `apps/worker/src/worker/consumers/gear_sync.py`
- `apps/worker/src/worker/jobs/source_sync.py`

### Implementation Notes
- Create apps/t3k_sync/ workspace member: pyproject.toml, src/t3k_sync/__init__.py, src/t3k_sync/main.py (FastAPI with /health endpoint and lifespan startup for consumer + scheduler), src/t3k_sync/consumer.py (pgmq consumer for gear_sync queue using consumer_base from core), src/t3k_sync/scheduler.py (embedded cron-like scheduler for ensure_sync_running, replaces apps/scheduler/). The agent MUST create the apps/t3k_sync/ directory structure.
- Create apps/audio_worker/ workspace member: pyproject.toml, src/audio_worker/__init__.py, src/audio_worker/main.py (FastAPI with /health endpoint and lifespan startup for consumer), src/audio_worker/consumer.py (pgmq consumer for process_audio queue). The agent MUST create the apps/audio_worker/ directory structure.
- Create apps/video_worker/ workspace member: pyproject.toml, src/video_worker/__init__.py, src/video_worker/main.py (FastAPI with /health endpoint and lifespan startup for consumer), src/video_worker/consumer.py (pgmq consumer for render_video queue). The agent MUST create the apps/video_worker/ directory structure.
- Move sync logic from apps/worker/jobs/source_sync.py and apps/scheduler/schedules/source_sync.py into t3k_sync/
- Move audio processing logic from apps/worker/jobs/audio_processing.py into audio_worker/consumer.py
- Move video/shootout job logic from apps/worker/jobs/shootout.py into video_worker/consumer.py
- infrastructure/docker/Dockerfile.t3k-sync — based on Dockerfile.dev pattern, runs t3k_sync app
- infrastructure/docker/Dockerfile.audio-worker — based on Dockerfile.dev pattern, runs audio_worker app
- Video worker extends existing Dockerfile.remotion (already exists) — update docker-compose to wire it
- Add t3k-sync, audio-worker, video-worker services to docker-compose.yml on jobs profile with health checks
- Delete apps/scheduler/ directory entirely — scheduling is now embedded in t3k-sync
- Remove scheduler service from docker-compose.yml
- Update pyproject.toml workspace members to add new apps, remove scheduler
- Remove sync-related code from monolithic worker (jobs/source_sync.py, consumers/gear_sync.py) but keep worker alive for now (removed in Story 04)

### Validation Checkpoint

After this story, a **process** validation will verify:
- Docker services start without errors including new BC containers (evidence: command, exit_code, output_tail)
- Lint and type checks pass with new packages (evidence: command, exit_code, output_tail)
