---
github_issue: 112
title: "Phase 5 Features — Audio Processing, Job Progress, Playback, Video (5C/5E/5F/5V)"
state: OPEN
labels: ["epic"]
fetched: 2026-02-17T20:02:29Z
---

## Epic: Phase 5 Features — Audio Processing, Job Progress, Playback, Video (5C/5E/5F/5V)

Wire up user-facing features that consume the data pipeline: shootout audio processing (5C), real-time job progress (5E), audio playback and comparison (5F), and video rendering (5V).

### Context

The job system (5A) and data pipeline (5B/5D) are operational. The audio processing library (`libs/audio` — ChainExecutor, NAM, IR, effects, EBU R128 normalisation) is complete from Phase 3B. The Video BC infrastructure (`libs/video`) was delivered in epic #70. This epic integrates them into the worker job system and webapp, delivering end-to-end user-facing functionality.

### Pre-requisites

- Epic #95 — Phase 4 Completion (4C shootout workflow for processing trigger)
- Epic #111 — Phase 5 Pipeline (5A job enqueue, 5B source data)

---

## Current State (Validated 2026-02-17, commit `3979fb4c`)

### What exists and works

| Component | Status | Evidence |
|-----------|--------|----------|
| Worker admin enqueue endpoint | Done | `POST /api/admin/enqueue` dispatches SHOOTOUT, SHOOTOUT_AUDIO, SHOOTOUT_MASTER job types (`apps/worker/src/worker/admin.py:479`) |
| Parent SHOOTOUT → N × SHOOTOUT_AUDIO child spawning | Done | Child creation + dispatch with idempotency checks (`apps/worker/src/worker/jobs/shootout.py:141-198`) |
| SHOOTOUT_MASTER orchestration | Done | Created after all audio children complete, with failure handling (`apps/worker/src/worker/jobs/shootout.py:63-138`) |
| Master audio creation | Done | Concatenation + chapter markers + status update (`apps/worker/src/worker/jobs/master_audio.py:157-179`) |
| Redis pub/sub progress publisher | Done (unused) | `publish_progress()` exists (`apps/worker/src/worker/progress.py:17-78`) — zero imports in handlers |
| HTMX job status fragment | Done | `GET /api/v1/html/jobs/{id}` with polling (`apps/webapp/src/webapp/api/v1/html.py:1370-1408`) |
| Video BC HTTP client + API scaffolds | Done | `libs/video/src/video/client.py` and `libs/video/src/video/api.py` |
| Shootout detail page with chains | Done | SSR page + HTMX fragments (`apps/webapp/src/webapp/api/pages.py`, `frontend/astro/`) |
| DI track audio streaming | Done | `GET /api/v1/di-tracks/{id}/stream` (`apps/webapp/src/webapp/api/v1/di_tracks.py:190`) |
| nginx WebSocket proxy support | Done | Upgrade headers on `/api/` location block (`nginx.conf.template:70-73`) |

### Bugs to fix (blocking)

| # | Bug | Details | Impact |
|---|-----|---------|--------|
| B1 | **Shootout status mismatch** | Repository creates shootouts with `PENDING` (`shootout_repository.py:205`). Process endpoint requires `DRAFT` (`shootouts.py:280`). No code path ever sets `DRAFT`. | **Blocks all processing** — users cannot trigger shootout processing. |
| B2 | **Enqueue call ignores failures** | `processing_service.py:22` — no `raise_for_status()`. HTTP errors silently swallowed. | Silent enqueue failures — user thinks processing started but nothing happens. |
| B3 | **Video BC route mismatch** | Client: `/api/v1/render/submit`, `/api/v1/render/status/{id}` (`client.py:64,92`). Server: `/render`, `/render/{id}` (`api.py:28,48`). | Video client gets 404 — video rendering cannot work. |
| B4 | **output_path rendered as `<video>` src** | `detail.html.ts:35-41` renders `shootout.output_path` (master audio) in `<video>` element. `html.py:95` conflates `output_path` and `video_path`. | Browser tries to play FLAC as video — broken playback. |
| B5 | **Stale WebSocket reference** | `base.astro:99` connects to `/api/v1/ws/notifications` — endpoint does not exist, no backend sets `ws_token`. | Silent JS errors on every page load for authenticated users. |
| B6 | **N+1 query in shootout detail** | `pages.py:732-736` issues separate query per chain instead of `joinedload`. | Unnecessary DB load, violates architecture query pattern. |
| B7 | **Publisher silently drops messages** | `publisher.py:106` — `contextlib.suppress(Exception)` around pgmq enqueue. | Gear sync data silently lost. |
| B8 | **Scheduler imports source adapter** | `auth.py:124-125` imports `source_t3k.adapters.inbound` — violates BC rules. | Architecture boundary drift. |

### Vocabulary drift (must resolve)

| Concept | Issue/docs | Code | Resolution |
|---------|-----------|------|------------|
| Video job type | `VIDEO_COMPOSE` | `VIDEO_COMPOSITION` (`job_status.py:83`) | Rename enum to `VIDEO_COMPOSE` |
| Shootout status | `processing` | Both `RUNNING` and `PROCESSING` in enum (`shootout.py:33-34`) | Remove `RUNNING`, keep only `PROCESSING` |

### What is not started

- WebSocket job progress endpoint (`/ws/jobs/{job_id}`)
- Progress publisher wired to job handlers
- Waveform data on AudioSegment model
- `/jobs` SSR page route in webapp + nginx
- Job history/list page
- Retry action for failed jobs
- All 5F endpoints (metadata, metrics, comparison)
- Audio player, segment playback, A/B comparison, audio download
- VIDEO_COMPOSE worker handler
- Video composition props generation
- Video render status polling, `shootout.video_status` updates
- Shootout completion gated by audio + video
- Video playback on shootout detail

---

## Architectural Decisions

### D1. Shootout state machine

Canonical flow: **`DRAFT → PENDING → PROCESSING → COMPLETED | FAILED`**

- New shootouts are created with status `DRAFT`.
- `POST /{id}/process` transitions `DRAFT → PENDING` and enqueues to worker.
- Worker sets `PROCESSING` when work begins.
- Worker sets `COMPLETED` only after both audio and video stages succeed (or `FAILED` on error).
- Remove `RUNNING` from `ShootoutStatus` enum — use `PROCESSING` consistently.

### D2. Job type vocabulary

Rename `JobType.VIDEO_COMPOSITION` → `JobType.VIDEO_COMPOSE`. Alembic migration to update persisted `video_composition` values to `video_compose`.

### D3. Artifact path semantics

- `output_path` = master audio FLAC path. Served via `GET /api/v1/shootouts/{id}/audio/master`.
- `video_path` = rendered MP4 path. Served via `GET /api/v1/shootouts/{id}/video`.
- Never expose raw filesystem paths to the frontend. Always use API serving endpoints with ownership checks.

### D4. Realtime transport

- Primary: WebSocket at `/ws/jobs/{job_id}` with JWT query-param auth and ownership validation.
- Fallback: HTMX polling via existing `GET /api/v1/html/jobs/{id}` fragment.
- nginx already has WebSocket upgrade headers on `/api/` location block.

### D5. BC dependency policy

Scheduler and worker MUST NOT import from `sources/*`. Scheduler's T3K token refresh must be refactored: move to worker (which bridges sources via pgmq) or extract to a core-level port.

### D6. File serving

Audio/video artifacts served through authenticated API endpoints with `FileResponse` and ownership checks. No direct filesystem path exposure.

### D7. Publisher error policy

Remove `contextlib.suppress(Exception)` from pgmq publisher. Publish failure = hard failure for the sync unit of work. No silent suppression.

---

## Dependency Graph

```
Wave 0:  Contract fixes (vocabulary, status, routes, bugs B1-B8)
         │
Wave 1:  5C end-to-end processing (waveform, N+1 fix, UI trigger)
         │
Wave 2:  5E real-time progress (WebSocket, /jobs pages, retry)
         │
Wave 3:  5F audio playback & comparison (player, A/B, metrics, download)
         │
Wave 4:  5V video rendering pipeline (VIDEO_COMPOSE handler, completion gate)
         │
Wave 5:  Hardening (BC enforcement, publisher fix, scheduler fix)
         │
Wave 6:  Verification & quality gates
```

---

## Implementation Plan

### Wave 0 — Contract and Vocabulary Harmonisation

> Fix all vocabulary drift, status mismatches, and route mismatches so subsequent waves build on a consistent foundation.

#### 0.1 Fix shootout status enum and creation path

**Files:**
- `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
  - Remove `RUNNING = "running"` from `ShootoutStatus` enum.
  - Change ORM column default from `ShootoutStatus.PENDING` to `ShootoutStatus.DRAFT` (line 145).
- `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`
  - Line 205: map `is_processed=False` → `ShootoutStatus.DRAFT` (was `PENDING`).
- `apps/webapp/src/webapp/api/v1/html.py`
  - Remove `_shootout_status_value()` normalisation function (lines 63-68) — no longer needed.
  - Update callers to use `status.value` directly.
- Alembic migration: update existing `running` values → `processing` in `shootouts` table.

**Done when:** New shootouts have `DRAFT` status. `POST /process` accepts `DRAFT` and transitions to `PENDING`.

#### 0.2 Rename VIDEO_COMPOSITION → VIDEO_COMPOSE

**Files:**
- `libs/core/src/core/domain/value_objects/job_status.py` line 83: `VIDEO_COMPOSITION` → `VIDEO_COMPOSE`, value `"video_composition"` → `"video_compose"`.
- Grep and update all references to `VIDEO_COMPOSITION` or `video_composition`.
- Alembic migration: update persisted `video_composition` → `video_compose` in `jobs` table.

**Done when:** Single canonical name `VIDEO_COMPOSE` everywhere.

#### 0.3 Fix video BC client/server route mismatch

**Files:**
- `libs/video/src/video/client.py`
  - Line 64: `/api/v1/render/submit` → `/render`
  - Line 92: `/api/v1/render/status/{job_id}` → `/render/{job_id}`

**Done when:** Client routes match server routes.

#### 0.4 Fix artifact path semantics in templates

**Files:**
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts` lines 35-41: render `video_path` in `<video>` element (not `output_path`). Show `<audio>` element for `output_path` if present.
- `apps/webapp/src/webapp/api/v1/html.py` line 95: pass `video_path` and `output_path` as separate context values — do not conflate them.

**Done when:** Audio in `<audio>`, video in `<video>`. No cross-contamination.

#### 0.5 Fix enqueue error handling

**Files:**
- `apps/webapp/src/webapp/services/processing_service.py` lines 22-25: add `response.raise_for_status()`. Wrap in try/except to raise `HTTPException(502)` on worker communication failure.

**Done when:** Enqueue failures propagate as HTTP errors to the caller.

#### 0.6 Remove stale WebSocket reference

**Files:**
- `frontend/astro/src/pages/layouts/base.astro` lines 88-145: remove the entire stale WebSocket IIFE script block connecting to `/api/v1/ws/notifications`.
- `frontend/astro/src/pages/partials/header.html.ts` line 25: remove `data-ws-token="{{ ws_token }}"`.
- Rebuild Astro: `just build-astro`.

**Done when:** No stale WebSocket connection attempts. No JS console errors.

---

### Wave 1 — 5C End-to-End Shootout Processing

> Complete the processing pipeline so users can trigger processing from the UI and get results.

#### 1.1 Add waveform column to AudioSegment

**Files:**
- `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`: add `waveform: Mapped[Any] = mapped_column(WaveformDataType(), nullable=True)` to `AudioSegment` after `peak_dbfs` (line 266).
- Alembic migration: add `waveform` column to `audio_segments` table.

**Done when:** AudioSegment model stores waveform data.

#### 1.2 Persist waveform data during audio processing

**Files:**
- `apps/worker/src/worker/jobs/audio.py`: after processing each chain, extract waveform data and include in the segment upsert.

**Done when:** Processed segments have populated `waveform` data.

#### 1.3 Fix N+1 query in shootout detail page

**Files:**
- `apps/webapp/src/webapp/api/pages.py` lines 732-736: replace per-chain `select(SignalChainModel)` loop with `joinedload(ShootoutChain.signal_chain)` in the initial query.

**Done when:** Shootout detail loads all chain data in a single query.

#### 1.4 Wire process trigger to UI

**Files:**
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`: add "Process Shootout" button visible when status is `draft` and chains exist. Triggers `POST /api/v1/shootouts/{id}/process` via HTMX or fetch. On success, show job progress or redirect.

**Done when:** User can click "Process" on a draft shootout with chains → processing starts.

---

### Wave 2 — 5E Real-time Job Progress

> Deliver live per-chain progress via WebSocket with HTMX polling fallback.

#### 2.1 Create WebSocket endpoint

**Files:**
- `apps/webapp/src/webapp/api/v1/ws.py` (create):
  - `GET /ws/jobs/{job_id}` WebSocket endpoint
  - JWT auth via `?token=` query param
  - Job ownership validation (`job.user_id == current_user.id`)
  - Subscribe to Redis pub/sub channel `job_progress:{job_id}`
  - Forward progress messages to client
  - Auto-close on terminal state
- `apps/webapp/src/webapp/main.py`: import and include the WS router.

**Done when:** Authenticated owners can connect and receive real-time progress.

#### 2.2 Wire progress publisher to job handlers

**Files:**
- `apps/worker/src/worker/jobs/shootout.py`: call `publish_progress()` at job start and after each child dispatch.
- `apps/worker/src/worker/jobs/audio.py`: publish at start, processing, normalisation, complete.
- `apps/worker/src/worker/jobs/master_audio.py`: publish at creation stages.

**Done when:** Redis pub/sub receives progress events. WebSocket clients see live updates.

#### 2.3 Create /jobs SSR page route

**Files:**
- `apps/webapp/src/webapp/api/pages.py`: add `GET /jobs/{job_id}` page route with ownership check, rendering the job detail page.
- `infrastructure/nginx/nginx.conf.template`: add `location /jobs` block proxying to webapp.

**Done when:** `/jobs/{uuid}` renders job detail page for the authenticated owner.

#### 2.4 Create jobs list/history page

**Files:**
- `apps/webapp/src/webapp/api/pages.py`: add `GET /jobs` page route listing user's active and recent jobs, ordered by `created_at desc`.
- Jinja2 template: show job type, status, progress, creation time, link to detail. Active jobs at top.

**Done when:** `/jobs` shows a list of the user's jobs with links to detail pages.

#### 2.5 Add retry action for failed jobs

**Files:**
- `apps/webapp/src/webapp/api/v1/jobs.py`: add `POST /api/v1/jobs/{job_id}/retry`. Validate `FAILED` status + ownership. Transition to `PENDING` and re-enqueue.
- Job detail template: show "Retry" button when status is `FAILED`.

**Done when:** Users can retry failed jobs. Transition `FAILED → PENDING` works.

#### 2.6 Update frontend WebSocket integration

**Files:**
- `frontend/astro/src/pages/layouts/base.astro` (or job templates): WebSocket connection for job pages, connecting to `/ws/jobs/{job_id}`. Update progress display on messages. Fall back to HTMX polling on failure.

**Done when:** Job detail page shows live progress. Falls back gracefully.

---

### Wave 3 — 5F Audio Playback & Comparison

> Users can play processed audio, compare chains A/B, view metrics, and download files.

#### 3.1 Create audio serving endpoints

**Files:**
- `apps/webapp/src/webapp/api/v1/shootouts.py` (or dedicated file):
  - `GET /api/v1/shootouts/{id}/audio/master` — stream master FLAC with ownership check.
  - `GET /api/v1/shootouts/{id}/chains/{chain_id}/audio` — stream per-chain audio with ownership check.
  - Return `FileResponse` with correct content types and `Content-Disposition` headers.

**Done when:** Authenticated owners can stream/download master and per-chain audio.

#### 3.2 Create metrics and comparison endpoints

**Files:**
- `apps/webapp/src/webapp/api/v1/metrics.py` (create):
  - `GET /api/v1/shootouts/{id}/metadata` — reproducibility metadata (software versions, audio settings, normalisation params, chain configs).
  - `GET /api/v1/shootouts/{id}/segments/{position}/metrics` — per-segment audio metrics (duration, LUFS, peak, waveform) + chain config.
  - `GET /api/v1/shootouts/{id}/comparison` — all segments with computed averages for comparison.
  - All endpoints enforce ownership.
- `apps/webapp/src/webapp/main.py`: include metrics router.
- Pydantic response schemas in `apps/webapp/src/webapp/api/v1/schemas/`.

**Done when:** All three endpoints return correct data for processed shootouts.

#### 3.3 Build audio player and comparison UI

**Files:**
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`:
  - Replace "deferred" placeholder tabs with real content.
  - **Playback tab:** HTML5 `<audio>` player per segment + waveform visualisation.
  - **Comparison tab:** A/B chain selectors, synchronised playback, quick-switch.
  - **Metrics tab:** Per-segment metrics from `/comparison` endpoint.
  - **Technical tab:** Metadata from `/metadata` endpoint.
  - Download links for segments and master FLAC.

**Done when:** Shootout detail has functional audio player, A/B comparison, waveform, metrics, downloads.

---

### Wave 4 — 5V Video Rendering Pipeline

> After audio processing, render a video. Shootout completes only when both audio and video succeed.

#### 4.1 Create VIDEO_COMPOSE job handler

**Files:**
- `apps/worker/src/worker/jobs/video_compose.py` (create):
  - `handle_video_compose_job(job_id)` TaskIQ handler.
  - Load shootout with chains, segments, gear.
  - Build Remotion composition props (`libs/video/props.py`).
  - Prepare gear images (`libs/video/image_prep.py`).
  - Submit render via `HttpVideoRenderClient.submit_render()`.
  - Poll `poll_status()` until terminal state.
  - Success: set `shootout.video_path`, `shootout.video_status = "completed"`.
  - Failure: set `shootout.video_status = "failed"`, mark job `FAILED`.
  - Publish progress at each stage.

**Done when:** VIDEO_COMPOSE job renders video from shootout data and stores result.

#### 4.2 Register VIDEO_COMPOSE in worker dispatch

**Files:**
- `apps/worker/src/worker/admin.py`: add `JobType.VIDEO_COMPOSE` branch dispatching to `handle_video_compose_job`.
- Worker imports: ensure TaskIQ discovers the handler.

**Done when:** Worker receives and dispatches VIDEO_COMPOSE jobs.

#### 4.3 Gate shootout completion on audio + video

**Files:**
- `apps/worker/src/worker/jobs/master_audio.py`: after master audio success, DO NOT mark shootout `COMPLETED`. Instead create and enqueue a `VIDEO_COMPOSE` child job. Shootout stays `PROCESSING`.
- `apps/worker/src/worker/jobs/video_compose.py`: on video success, mark parent SHOOTOUT job `COMPLETED`, set `shootout.status = COMPLETED`. On failure, mark `FAILED`.

**Updated job hierarchy:**
```
SHOOTOUT (parent)
├── SHOOTOUT_AUDIO (chain A) ─┐
├── SHOOTOUT_AUDIO (chain B) ─┼── parallel per-chain
├── SHOOTOUT_AUDIO (chain C) ─┘
├── SHOOTOUT_MASTER ───────────── after all audio complete
└── VIDEO_COMPOSE ─────────────── after SHOOTOUT_MASTER (final step)
```

**Done when:** Shootout is `COMPLETED` only after both audio AND video succeed.

#### 4.4 Add video playback to shootout detail

**Files:**
- `apps/webapp/src/webapp/api/v1/shootouts.py`: `GET /api/v1/shootouts/{id}/video` — stream MP4 with ownership check.
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`: `<video>` element with `src="/api/v1/shootouts/{id}/video"` when `video_path` exists. Show progress when `video_status` is not complete.

**Done when:** Completed shootouts show rendered video player via authenticated endpoint.

---

### Wave 5 — Hardening and BC Enforcement

> Close architectural debt and reliability risks.

#### 5.1 Fix publisher error suppression

**Files:**
- `sources/t3k/src/source_t3k/adapters/outbound/publisher.py` line 106: remove `contextlib.suppress(Exception)`. Let exceptions propagate. Add logging before propagation.

**Done when:** Publish failures cause sync unit of work to fail. No silent data loss.

#### 5.2 Fix scheduler BC dependency violation

**Files:**
- `apps/scheduler/src/scheduler/schedules/auth.py` lines 124-125: remove `source_t3k.adapters.inbound` imports. Move token refresh to worker or extract to core-level port.

**Done when:** Scheduler has zero imports from `sources/*`.

#### 5.3 Enforce BC boundaries with import-linter

**Files:**
- `pyproject.toml`: add/update import-linter contracts enforcing:
  - `scheduler` cannot import `source_t3k`, `audio`, `video`
  - `worker` cannot import `source_t3k` (consumes via pgmq)
  - `webapp` cannot import `source_t3k`

**Done when:** `just check` passes with import-linter contracts enforced.

#### 5.4 Add scheduler startup self-check

**Files:**
- `apps/scheduler/src/scheduler/main.py`: on startup, log all discovered scheduled functions and intervals. Fail fast if zero tasks registered.

**Done when:** Scheduler logs its schedule on startup. Missing schedules cause failure.

---

### Wave 6 — Verification and Quality Gates

#### Automated checks (mandatory)

```bash
just check            # lint, types, import-linter
just test-regression  # all regression tests
just test-golden-path # end-to-end golden path
```

#### Manual integration verification

- [ ] Create shootout → status is `draft`
- [ ] Add chains → chains appear in detail
- [ ] Click "Process" → job created, `draft → pending → processing`
- [ ] Worker processes all chains → segments stored with waveform data
- [ ] Master audio created with chapter markers
- [ ] VIDEO_COMPOSE triggers → video renders
- [ ] Shootout marked `completed` only after audio + video done
- [ ] WebSocket shows live per-chain progress
- [ ] `/jobs` page shows active and recent jobs
- [ ] Failed jobs show error with retry button
- [ ] Retry re-enqueues successfully
- [ ] Audio player plays segments on shootout detail
- [ ] A/B comparison switches between chains in sync
- [ ] Metrics endpoints return correct data
- [ ] Audio download works (segments + master FLAC)
- [ ] Video player shows on completed shootout
- [ ] Full flow: create → add chains → process → listen → watch video

---

## Key Files Reference

| File | Action | Wave |
|------|--------|------|
| `libs/core/src/core/domain/value_objects/job_status.py` | Edit — rename VIDEO_COMPOSITION → VIDEO_COMPOSE | 0 |
| `apps/webapp/src/webapp/adapters/persistence/models/shootout.py` | Edit — fix status enum, add waveform column | 0, 1 |
| `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py` | Edit — create with DRAFT status | 0 |
| `apps/webapp/src/webapp/api/v1/html.py` | Edit — remove status normalisation, fix artifact paths | 0 |
| `apps/webapp/src/webapp/services/processing_service.py` | Edit — add raise_for_status | 0 |
| `libs/video/src/video/client.py` | Edit — fix route paths | 0 |
| `frontend/astro/src/pages/layouts/base.astro` | Edit — remove stale WS, add correct WS | 0, 2 |
| `frontend/astro/src/pages/fragments/shootouts/detail.html.ts` | Edit — fix video/audio, add player/comparison | 0, 1, 3 |
| `apps/webapp/src/webapp/api/pages.py` | Edit — fix N+1 query, add /jobs routes | 1, 2 |
| `apps/worker/src/worker/jobs/audio.py` | Edit — persist waveform, publish progress | 1, 2 |
| `apps/worker/src/worker/jobs/shootout.py` | Edit — publish progress | 2 |
| `apps/worker/src/worker/jobs/master_audio.py` | Edit — publish progress, gate on video | 2, 4 |
| `apps/webapp/src/webapp/api/v1/ws.py` | **Create** — WebSocket endpoint | 2 |
| `apps/webapp/src/webapp/api/v1/metrics.py` | **Create** — metadata, metrics, comparison | 3 |
| `apps/webapp/src/webapp/api/v1/shootouts.py` | Edit — add audio/video serving | 3, 4 |
| `apps/worker/src/worker/jobs/video_compose.py` | **Create** — VIDEO_COMPOSE handler | 4 |
| `apps/worker/src/worker/admin.py` | Edit — add VIDEO_COMPOSE dispatch | 4 |
| `sources/t3k/src/source_t3k/adapters/outbound/publisher.py` | Edit — remove silent suppression | 5 |
| `apps/scheduler/src/scheduler/schedules/auth.py` | Edit — remove source imports | 5 |
| `pyproject.toml` | Edit — add import-linter contracts | 5 |
| `infrastructure/nginx/nginx.conf.template` | Edit — add /jobs location block | 2 |

---

## Deferred

- **Phase 5G (AI Tone Evaluation)** — separate future epic after 5F
- **Phase 6 (E2E Integration)** — separate epic after all Phase 5
- **Phase 7 (Developer Tooling & Ops)** — final epic

## References

- [IMPLEMENTATION.md](../wiki/IMPLEMENTATION.md) — Phases 5C, 5E, 5F, 5V
- [GTS-Technical-Architecture](../wiki/GTS-Technical-Architecture.md) — Job scheduling, audio processing, video rendering
- [GTS-Remotion-Architecture](../wiki/GTS-Remotion-Architecture.md) — Video BC details
