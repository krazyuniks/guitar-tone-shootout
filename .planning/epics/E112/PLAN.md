# Plan: Epic #112

## Goal

Users can trigger shootout audio processing, monitor job progress in real-time, play back and compare processed audio segments, and watch rendered comparison videos — delivering the full end-to-end shootout experience from creation to playback.

## Observable Truths

1. When a user creates a new shootout, its status displays as 'Draft' on the shootout detail page.
2. A user can click 'Process' on a draft shootout that has chains, and the status transitions from Draft through Pending to Processing.
3. While a shootout is processing, the user sees live progress updates on the job detail page via WebSocket (with HTMX polling fallback).
4. A user can visit /jobs and see a list of their active and recent jobs with type, status, and creation time.
5. A user can click a job in the list to view its detail page showing progress, status, and error information.
6. A user can click 'Retry' on a failed job, which re-enqueues it and transitions status back to Pending.
7. On a completed shootout's detail page, a user can play processed audio segments using an HTML5 audio player.
8. A user can select two chains for A/B comparison with synchronised playback and quick-switch between them.
9. A user can view per-segment audio metrics including duration, LUFS, and peak dBFS on the shootout detail page.
10. A user can download individual segment audio files and the master FLAC from the shootout detail page.
11. A completed shootout with a rendered video shows a video player on the detail page.
12. A shootout's status only transitions to 'Completed' after both audio processing and video rendering have succeeded.
13. If the worker is unreachable when a user clicks 'Process', an error message is shown instead of silently failing.
14. Authenticated users loading any page see no JavaScript console errors from stale WebSocket connection attempts.

## User Journeys

### Journey J1: Authenticated user with a shootout containing signal chains

The user navigates to their shootout detail page and sees the status is 'Draft'. They click the 'Process' button, which triggers audio processing. The status changes to 'Pending' then 'Processing'. They are directed to the job detail page where they see live progress updates via WebSocket as each chain is processed. After all audio chains complete, the master audio is created and video rendering begins automatically. The shootout status only becomes 'Completed' once both audio and video succeed. They return to the shootout detail page and see the video player with the rendered comparison video. Throughout this flow, no stale WebSocket errors appear in the console.

**Truths covered:** 1, 2, 3, 11, 12, 13, 14
**Entry point:** /shootout/{id}
**Critical transitions:**
- Shootout detail page (Draft status) -> Shootout detail page (Pending/Processing status) (Click 'Process' button, POST /api/v1/shootouts/{id}/process)
- Shootout detail page -> Job detail page (Click job link or redirect after process trigger)
- Job detail page -> Job detail page (updated progress) (WebSocket message updates progress display in real-time)
- Job detail page (Completed) -> Shootout detail page (Click link back to shootout)
- Shootout detail page (Completed) -> Video playback (Video player loads /api/v1/shootouts/{id}/video)

### Journey J2: Authenticated user checking job history and retrying failures

The user navigates to /jobs and sees a list of their active and recent jobs showing type, status, progress, and creation time. They click on a specific job to see its detail page with full progress information. They notice a failed job, see the error message, and click the 'Retry' button. The job transitions back to 'Pending' and is re-enqueued for processing. They return to the jobs list and see the job is now active again.

**Truths covered:** 4, 5, 6
**Entry point:** /jobs
**Critical transitions:**
- /jobs list page -> /jobs/{id} detail page (Click job row link)
- Job detail page (Failed status) -> Job detail page (Pending status) (Click 'Retry' button, POST /api/v1/jobs/{id}/retry)
- Job detail page -> /jobs list page (Click 'Back to Jobs' link)

### Journey J3: Authenticated user reviewing completed shootout audio

The user navigates to a completed shootout's detail page. They see the Playback tab with an HTML5 audio player for each processed segment, showing waveform visualisation. They play individual segments. They switch to the Comparison tab, select two chains for A/B comparison, and use synchronised playback with quick-switch to compare tones. They check the Metrics tab to see per-segment audio metrics (duration, LUFS, peak dBFS). They click download links to save individual segment audio files and the master FLAC to their computer.

**Truths covered:** 7, 8, 9, 10
**Entry point:** /shootout/{id}
**Critical transitions:**
- Shootout detail page -> Playback tab (Click 'Playback' tab)
- Playback tab -> Audio playing (Click play button on audio player, loads /api/v1/shootouts/{id}/chains/{chain_id}/audio)
- Playback tab -> Comparison tab (Click 'Comparison' tab)
- Comparison tab -> A/B synchronised playback (Select two chains, click play, use quick-switch buttons)
- Shootout detail page -> Metrics tab (Click 'Metrics' tab)
- Shootout detail page -> File download (Click download link for segment or master audio)

## Stories

### Story: Contract and Vocabulary Fixes (`01-contract-fixes`)

**Purpose:** Fix all blocking bugs (B1-B8), vocabulary drift, and architectural debt so subsequent stories build on a consistent, working foundation. This includes shootout status enum fixes, video route mismatch, enqueue error handling, stale WebSocket removal, publisher error suppression, scheduler BC violation, and import-linter contracts.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, gts-frontend-dev, gts-testing]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Modify: `apps/webapp/src/webapp/services/processing_service.py`
- Modify: `libs/core/src/core/domain/value_objects/job_status.py`
- Modify: `libs/video/src/video/client.py`
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`
- Modify: `frontend/astro/src/pages/layouts/base.astro`
- Modify: `frontend/astro/src/pages/partials/header.html.ts`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`
- Modify: `apps/scheduler/src/scheduler/schedules/auth.py`
- Modify: `apps/scheduler/src/scheduler/main.py`
- Modify: `pyproject.toml`

**Wiki Sections:** GTS-Technical-Architecture :: domain-model, GTS-Technical-Architecture :: design-patterns, GTS-Technical-Architecture :: data-ingestion, GTS-Technical-Architecture :: infrastructure

**Implementation Notes:**
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

**Truths Addressed:** 1, 13, 14

---

### Validation Checkpoint: After Contract and Vocabulary Fixes

**Type:** quality
**Checks:**
- Import-linter contracts pass: scheduler has zero imports from sources/*, worker has zero imports from source_t3k, webapp has zero imports from source_t3k. (evidence: commands_run, exit_code, error_count)
- Astro build succeeds after removing stale WebSocket script block from base.astro. (evidence: commands_run, exit_code, error_count)
- ShootoutStatus enum no longer contains RUNNING. New shootouts created with DRAFT status. Alembic migrations apply cleanly. (evidence: commands_run, exit_code, error_count)

---

### Story: Processing Pipeline and Real-time Job Progress (`02-processing-and-progress`)

**Purpose:** Complete the shootout processing pipeline (waveform data, N+1 fix, process trigger UI) and deliver real-time job progress via WebSocket with HTMX polling fallback. Create /jobs pages for job history and retry. Wire progress publisher to job handlers.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, gts-frontend-dev, gts-auth]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/ws.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- Modify: `apps/webapp/src/webapp/api/pages.py`
- Modify: `apps/webapp/src/webapp/api/v1/jobs.py`
- Modify: `apps/webapp/src/webapp/main.py`
- Modify: `apps/worker/src/worker/jobs/audio.py`
- Modify: `apps/worker/src/worker/jobs/shootout.py`
- Modify: `apps/worker/src/worker/jobs/master_audio.py`
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`
- Modify: `frontend/astro/src/pages/layouts/base.astro`
- Modify: `frontend/astro/src/pages/jobs/index.astro`
- Modify: `infrastructure/nginx/nginx.conf.template`

**Wiki Sections:** GTS-Technical-Architecture :: architecture-layers, GTS-Technical-Architecture :: design-patterns, GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: frontend, GTS-Technical-Architecture :: auth, GTS-Technical-Architecture :: persistence, Audio-Processing

**Implementation Notes:**
- Add waveform column to AudioSegment model after peak_dbfs (nullable, WaveformDataType). Create Alembic migration to add column.
- In worker/jobs/audio.py, after processing each chain, extract waveform data using audio.analysis.waveform.extract_waveform() and include in segment upsert.
- Fix N+1 query in pages.py lines 732-736: replace per-chain select(SignalChainModel) loop with joinedload(ShootoutChain.signal_chain) in the initial query. Use .unique() on results.
- In detail.html.ts, add 'Process Shootout' button visible when status is 'draft' and chains exist. Trigger POST /api/v1/shootouts/{id}/process via HTMX or fetch. Include data-testid='process-shootout-btn'.
- Create WebSocket endpoint at /ws/jobs/{job_id} in ws.py: JWT auth via ?token= query param, job ownership validation, subscribe to Redis pub/sub channel job_progress:{job_id}, forward messages to client, auto-close on terminal state.
- Register WS router in main.py.
- Wire progress publisher in worker jobs: call publish_progress() at job start, after each child dispatch (shootout.py), at processing/normalisation/complete stages (audio.py), and at master creation stages (master_audio.py).
- Add GET /jobs/{job_id} page route in pages.py with ownership check. Add GET /jobs page route listing user's active and recent jobs ordered by created_at desc.
- Add /jobs location block in nginx.conf.template proxying to webapp.
- Add POST /api/v1/jobs/{job_id}/retry endpoint in jobs.py: validate FAILED status + ownership, transition to PENDING, re-enqueue.
- Update jobs/index.astro or create Jinja2 template for jobs list page showing job type, status, progress, creation time, links to detail. Active jobs at top.
- Add WebSocket connection logic for job pages in base.astro or job templates: connect to /ws/jobs/{job_id}, update progress display on messages, fall back to HTMX polling on failure.
- Show 'Retry' button on job detail when status is FAILED. Include data-testid='retry-job-btn'.
- Include data-testid attributes on all interactive elements: job-list, job-item, job-detail, retry-job-btn, process-shootout-btn.

**Truths Addressed:** 2, 3, 4, 5, 6

---

### Validation Checkpoint: After Processing Pipeline and Real-time Job Progress

**Type:** http+dom
**Checks:**
- Shootout detail page shows 'Process' button when status is Draft and chains exist. (evidence: status_code, url, dom_selector, element_text)
- /jobs page returns 200 for authenticated user and shows job list container. (evidence: status_code, url, dom_selector, element_text)
- WebSocket endpoint /ws/jobs/{job_id} accepts connections with valid JWT token query parameter. (evidence: status_code, url, dom_selector, element_text)
- POST /api/v1/jobs/{job_id}/retry returns 200 for a failed job owned by the authenticated user. (evidence: status_code, url, dom_selector, element_text)

---

### Story: Audio Playback, Comparison, and Metrics (`03-audio-playback`)

**Purpose:** Deliver audio serving endpoints, per-segment metrics and comparison endpoints, and the full shootout detail UI with audio player, A/B comparison, metrics display, and download functionality.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, gts-frontend-dev, gts-auth]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/metrics.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/metrics.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `apps/webapp/src/webapp/main.py`
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`

**Wiki Sections:** GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: auth, GTS-Technical-Architecture :: frontend, Audio-Processing, Frontend-Architecture

**Implementation Notes:**
- Add GET /api/v1/shootouts/{id}/audio/master endpoint in shootouts.py: stream master FLAC with FileResponse, ownership check, correct content type and Content-Disposition header.
- Add GET /api/v1/shootouts/{id}/chains/{chain_id}/audio endpoint: stream per-chain audio with ownership check.
- Create metrics.py with three endpoints: GET /api/v1/shootouts/{id}/metadata (reproducibility metadata: software versions, audio settings, normalisation params, chain configs), GET /api/v1/shootouts/{id}/segments/{position}/metrics (per-segment audio metrics: duration, LUFS, peak, waveform + chain config), GET /api/v1/shootouts/{id}/comparison (all segments with computed averages for comparison). All enforce ownership.
- Create Pydantic response schemas in schemas/metrics.py for metadata, segment metrics, and comparison responses.
- Register metrics router in main.py.
- Update detail.html.ts to replace deferred placeholder tabs with real content: Playback tab with HTML5 <audio> player per segment + waveform visualisation, Comparison tab with A/B chain selectors + synchronised playback + quick-switch, Metrics tab with per-segment metrics from /comparison endpoint, Technical tab with metadata from /metadata endpoint.
- Add download links for individual segments and master FLAC. Use the authenticated API endpoints, not raw file paths.
- All audio/video artifacts served through authenticated API endpoints with FileResponse. Never expose raw filesystem paths.
- Include data-testid attributes: audio-player, comparison-tab, metrics-tab, download-segment-btn, download-master-btn, ab-switch-btn.

**Truths Addressed:** 7, 8, 9, 10

---

### Validation Checkpoint: After Audio Playback, Comparison, and Metrics

**Type:** api+response
**Checks:**
- GET /api/v1/shootouts/{id}/audio/master returns audio file with correct Content-Type for an authenticated owner. (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/shootouts/{id}/chains/{chain_id}/audio returns per-chain audio with correct Content-Type. (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/shootouts/{id}/metadata returns JSON with software versions, audio settings, and chain configs. (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/shootouts/{id}/comparison returns JSON with all segments and computed averages. (evidence: status_code, url, method, response_body_excerpt)

---

### Story: Video Rendering Pipeline and Completion Gate (`04-video-pipeline`)

**Purpose:** Create the VIDEO_COMPOSE job handler, register it in worker dispatch, gate shootout completion on both audio and video success, and add video playback to the shootout detail page.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-backend-dev, gts-video, gts-frontend-dev]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 50
- max_budget_usd: 5.0

**Scope:**
- Create: `apps/worker/src/worker/jobs/video_compose.py`
- Modify: `apps/worker/src/worker/admin.py`
- Modify: `apps/worker/src/worker/jobs/master_audio.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`

**Wiki Sections:** GTS-Technical-Architecture :: architecture-layers, GTS-Technical-Architecture :: design-patterns, GTS-Remotion-Architecture, Audio-Processing

**Implementation Notes:**
- Create video_compose.py with handle_video_compose_job(job_id) TaskIQ handler: load shootout with chains/segments/gear, build Remotion composition props via libs/video/props.py, prepare gear images via libs/video/image_prep.py, submit render via HttpVideoRenderClient.submit_render(), poll poll_status() until terminal state.
- On success: set shootout.video_path, shootout.video_status = 'completed'. On failure: set shootout.video_status = 'failed', mark job FAILED.
- Publish progress at each stage of video rendering.
- In admin.py, add JobType.VIDEO_COMPOSE branch dispatching to handle_video_compose_job. Ensure TaskIQ discovers the handler.
- Modify master_audio.py: after master audio success, DO NOT mark shootout COMPLETED. Instead create and enqueue a VIDEO_COMPOSE child job. Shootout stays PROCESSING.
- In video_compose.py: on video success, mark parent SHOOTOUT job COMPLETED, set shootout.status = COMPLETED. On failure, mark FAILED.
- Job hierarchy: SHOOTOUT (parent) → N × SHOOTOUT_AUDIO (parallel) → SHOOTOUT_MASTER → VIDEO_COMPOSE (final step).
- Add GET /api/v1/shootouts/{id}/video endpoint in shootouts.py: stream MP4 with ownership check.
- In detail.html.ts, add <video> element with src pointing to /api/v1/shootouts/{id}/video when video_path exists. Show progress indicator when video_status is not complete.
- Include data-testid='video-player' on the video element.

**Truths Addressed:** 11, 12

---

### Validation Checkpoint: After Video Rendering Pipeline and Completion Gate

**Type:** api+response
**Checks:**
- Worker admin endpoint accepts VIDEO_COMPOSE job type dispatch. (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/shootouts/{id}/video endpoint exists and returns 404 when no video_path is set (not a 500 or routing error). (evidence: status_code, url, method, response_body_excerpt)
- Shootout detail page template renders <video> element when video_path is present and progress indicator when video_status is not complete. (evidence: status_code, url, method, response_body_excerpt)

---

### Story: Regression Tests and Quality Gates (`05-regression-tests`)

**Purpose:** Write regression tests covering the full shootout lifecycle, job progress, audio playback, and video rendering. Run all quality gates to verify the epic is complete.

**Agent:**
- model: sonnet
- skills: [gts-testing, gts-architecture]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Modify: `tests/regression/test_models.py`
- Modify: `tests/unit/webapp/test_shootout_status.py`
- Modify: `tests/unit/worker/test_job_handlers.py`
- Modify: `tests/unit/worker/test_video_compose.py`

**Wiki Sections:** GTS-Technical-Architecture :: infrastructure, GTS-Technical-Architecture :: design-patterns

**Implementation Notes:**
- Add regression tests verifying: ShootoutStatus enum has DRAFT/PENDING/PROCESSING/COMPLETED/FAILED (no RUNNING), JobType enum has VIDEO_COMPOSE (not VIDEO_COMPOSITION), AudioSegment model has waveform column.
- Add unit tests for shootout status transitions: DRAFT → PENDING on process trigger, PENDING → PROCESSING when worker starts, completion gated on audio + video.
- Add unit tests for job retry: FAILED → PENDING transition.
- Add unit tests for VIDEO_COMPOSE job handler dispatch.
- Run just check (lint, types, import-linter).
- Run just test-regression.
- Run just test-golden-path if E2E infrastructure is available.
- Verify all quality gates pass before marking epic complete.
- If test files don't exist yet, create them in the appropriate test directories.

**Truths Addressed:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14

---

### Validation Checkpoint: After Regression Tests and Quality Gates

**Type:** regression
**Checks:**
- All regression tests pass (just test-regression). (evidence: test_command, exit_code, test_count, failure_count)
- All quality gates pass (just check) including lint, types, and import-linter. (evidence: test_command, exit_code, test_count, failure_count)

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. When a user creates a new shootout, its status displays as 'Draft' on the shootout detail page. | `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`, `apps/webapp/src/webapp/api/v1/html.py` (+14 more) | Contract and Vocabulary Fixes, Regression Tests and Quality Gates |
| 2. A user can click 'Process' on a draft shootout that has chains, and the status transitions from Draft through Pending to Processing. | `apps/webapp/src/webapp/api/v1/ws.py`, `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/api/pages.py` (+13 more) | Processing Pipeline and Real-time Job Progress, Regression Tests and Quality Gates |
| 3. While a shootout is processing, the user sees live progress updates on the job detail page via WebSocket (with HTMX polling fallback). | `apps/webapp/src/webapp/api/v1/ws.py`, `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/api/pages.py` (+13 more) | Processing Pipeline and Real-time Job Progress, Regression Tests and Quality Gates |
| 4. A user can visit /jobs and see a list of their active and recent jobs with type, status, and creation time. | `apps/webapp/src/webapp/api/v1/ws.py`, `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/api/pages.py` (+13 more) | Processing Pipeline and Real-time Job Progress, Regression Tests and Quality Gates |
| 5. A user can click a job in the list to view its detail page showing progress, status, and error information. | `apps/webapp/src/webapp/api/v1/ws.py`, `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/api/pages.py` (+13 more) | Processing Pipeline and Real-time Job Progress, Regression Tests and Quality Gates |
| 6. A user can click 'Retry' on a failed job, which re-enqueues it and transitions status back to Pending. | `apps/webapp/src/webapp/api/v1/ws.py`, `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/api/pages.py` (+13 more) | Processing Pipeline and Real-time Job Progress, Regression Tests and Quality Gates |
| 7. On a completed shootout's detail page, a user can play processed audio segments using an HTML5 audio player. | `apps/webapp/src/webapp/api/v1/metrics.py`, `apps/webapp/src/webapp/api/v1/schemas/metrics.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+6 more) | Audio Playback, Comparison, and Metrics, Regression Tests and Quality Gates |
| 8. A user can select two chains for A/B comparison with synchronised playback and quick-switch between them. | `apps/webapp/src/webapp/api/v1/metrics.py`, `apps/webapp/src/webapp/api/v1/schemas/metrics.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+6 more) | Audio Playback, Comparison, and Metrics, Regression Tests and Quality Gates |
| 9. A user can view per-segment audio metrics including duration, LUFS, and peak dBFS on the shootout detail page. | `apps/webapp/src/webapp/api/v1/metrics.py`, `apps/webapp/src/webapp/api/v1/schemas/metrics.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+6 more) | Audio Playback, Comparison, and Metrics, Regression Tests and Quality Gates |
| 10. A user can download individual segment audio files and the master FLAC from the shootout detail page. | `apps/webapp/src/webapp/api/v1/metrics.py`, `apps/webapp/src/webapp/api/v1/schemas/metrics.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+6 more) | Audio Playback, Comparison, and Metrics, Regression Tests and Quality Gates |
| 11. A completed shootout with a rendered video shows a video player on the detail page. | `apps/worker/src/worker/jobs/video_compose.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/jobs/master_audio.py` (+6 more) | Video Rendering Pipeline and Completion Gate, Regression Tests and Quality Gates |
| 12. A shootout's status only transitions to 'Completed' after both audio processing and video rendering have succeeded. | `apps/worker/src/worker/jobs/video_compose.py`, `apps/worker/src/worker/admin.py`, `apps/worker/src/worker/jobs/master_audio.py` (+6 more) | Video Rendering Pipeline and Completion Gate, Regression Tests and Quality Gates |
| 13. If the worker is unreachable when a user clicks 'Process', an error message is shown instead of silently failing. | `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`, `apps/webapp/src/webapp/api/v1/html.py` (+14 more) | Contract and Vocabulary Fixes, Regression Tests and Quality Gates |
| 14. Authenticated users loading any page see no JavaScript console errors from stale WebSocket connection attempts. | `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`, `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`, `apps/webapp/src/webapp/api/v1/html.py` (+14 more) | Contract and Vocabulary Fixes, Regression Tests and Quality Gates |
