[GTS]|rules:{authentication,github}|skills:{gts-architecture,gts-backend-dev,gts-frontend-dev,gts-testing}|wiki:{api-design,audio,design-patterns,domain-model,frontend,persistence,testing}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 01-contract-fixes
**Name:** Contract and Vocabulary Fixes
**Purpose:** Fix all blocking bugs (B1-B8), vocabulary drift, and architectural debt so subsequent stories build on a consistent, working foundation. This includes shootout status enum fixes, video route mismatch, enqueue error handling, stale WebSocket removal, publisher error suppression, scheduler BC violation, and import-linter contracts.

### Scope
**Modify:**
- `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`
- `apps/webapp/src/webapp/api/v1/html.py`
- `apps/webapp/src/webapp/services/processing_service.py`
- `libs/core/src/core/domain/value_objects/job_status.py`
- `libs/video/src/video/client.py`
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`
- `frontend/astro/src/pages/layouts/base.astro`
- `frontend/astro/src/pages/partials/header.html.ts`
- `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`
- `apps/scheduler/src/scheduler/schedules/auth.py`
- `apps/scheduler/src/scheduler/main.py`
- `pyproject.toml`

### Implementation Notes
- Remove RUNNING from ShootoutStatus enum, keep only PROCESSING. Change ORM column default to DRAFT.
- In shootout_repository.py line 205, map is_processed=False to ShootoutStatus.DRAFT instead of PENDING.
- Remove _shootout_status_value() normalisation function from html.py (lines 63-68) and update callers to use status.value directly.
- Rename JobType.VIDEO_COMPOSITION to VIDEO_COMPOSE in job_status.py line 83. Grep and update all references.
- Create Alembic migrations: (a) update existing 'running' values to 'processing' in shootouts table + set default to 'draft', (b) update 'video_composition' to 'video_compose' in jobs table.
- Fix video client.py routes: /api/v1/render/submit → /render, /api/v1/render/status/{job_id} → /render/{job_id}.
- In detail.html.ts, render output_path in <audio> element and video_path in <video> element. In html.py line 95, pass them as separate context values.
- In processing_service.py, add response.raise_for_status() after the enqueue HTTP call. Wrap in try/except to raise HTTPException(502) on worker communication failure.
- Remove the entire stale WebSocket IIFE script block from base.astro (lines 88-145). Remove data-ws-token from header.html.ts line 25.
- In publisher.py line 106, remove contextlib.suppress(Exception). Let exceptions propagate. Add logging before propagation.
- In scheduler auth.py lines 124-125, remove source_t3k.adapters.inbound imports. Move token refresh logic to worker or extract to a core-level port.
- Add import-linter contracts to pyproject.toml: scheduler cannot import source_t3k/audio/video, worker cannot import source_t3k, webapp cannot import source_t3k.
- Add scheduler startup self-check in main.py: log all discovered scheduled functions and intervals, fail fast if zero tasks registered.
- Run just build-astro after frontend changes.
- Run just check to verify import-linter contracts pass.

### Validation Checkpoint

After this story, a **quality** validation will verify:
- Import-linter contracts pass: scheduler has zero imports from sources/*, worker has zero imports from source_t3k, webapp has zero imports from source_t3k. (evidence: commands_run, exit_code, error_count)
- Astro build succeeds after removing stale WebSocket script block from base.astro. (evidence: commands_run, exit_code, error_count)
- ShootoutStatus enum no longer contains RUNNING. New shootouts created with DRAFT status. Alembic migrations apply cleanly. (evidence: commands_run, exit_code, error_count)


---
## Failure Feedback (Attempt 2)

**Error:** One or more checks failed
**Files modified:** apps/webapp/src/webapp/adapters/persistence/models/shootout.py, apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py, apps/webapp/src/webapp/api/v1/html.py, apps/webapp/src/webapp/services/processing_service.py, libs/core/src/core/domain/value_objects/job_status.py, libs/video/src/video/client.py, frontend/astro/src/pages/fragments/shootouts/detail.html.ts, frontend/astro/src/pages/layouts/base.astro, frontend/astro/src/pages/partials/header.html.ts, sources/t3k/src/source_t3k/adapters/outbound/publisher.py, apps/scheduler/src/scheduler/schedules/auth.py, apps/scheduler/src/scheduler/main.py, pyproject.toml
**JSONL excerpt:** {"event": "validation_fail", "story_id": "01-contract-fixes", "attempt": 2, "check_type": "quality", "failure_category": "implementation", "failure_reason": "One or more checks failed", "evidence": "One or more checks failed"}
