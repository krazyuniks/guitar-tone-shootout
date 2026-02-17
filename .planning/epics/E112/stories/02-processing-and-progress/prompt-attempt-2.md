[GTS]|rules:{authentication,container-execution,github}|skills:{docker-infra,gts-architecture,gts-backend-dev,gts-frontend-dev}|wiki:{api-design,design-patterns,domain-model,frontend,infrastructure,persistence}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 02-processing-and-progress
**Name:** Processing Pipeline and Real-time Job Progress
**Purpose:** Complete the shootout processing pipeline (waveform data, N+1 fix, process trigger UI) and deliver real-time job progress via WebSocket with HTMX polling fallback. Create /jobs pages for job history and retry. Wire progress publisher to job handlers.

### Scope
**Create:**
- `apps/webapp/src/webapp/api/v1/ws.py`
**Modify:**
- `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- `apps/webapp/src/webapp/api/pages.py`
- `apps/webapp/src/webapp/api/v1/jobs.py`
- `apps/webapp/src/webapp/main.py`
- `apps/worker/src/worker/jobs/audio.py`
- `apps/worker/src/worker/jobs/shootout.py`
- `apps/worker/src/worker/jobs/master_audio.py`
- `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`
- `frontend/astro/src/pages/layouts/base.astro`
- `frontend/astro/src/pages/jobs/index.astro`
- `infrastructure/nginx/nginx.conf.template`

### Implementation Notes
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

### Validation Checkpoint

After this story, a **http+dom** validation will verify:
- Shootout detail page shows 'Process' button when status is Draft and chains exist. (evidence: status_code, url, dom_selector, element_text)
- /jobs page returns 200 for authenticated user and shows job list container. (evidence: status_code, url, dom_selector, element_text)
- WebSocket endpoint /ws/jobs/{job_id} accepts connections with valid JWT token query parameter. (evidence: status_code, url, dom_selector, element_text)
- POST /api/v1/jobs/{job_id}/retry returns 200 for a failed job owned by the authenticated user. (evidence: status_code, url, dom_selector, element_text)


---
## Failure Feedback (Attempt 1)

**Error:** {"type":"result","subtype":"error_max_turns","duration_ms":58002,"duration_api_ms":62302,"is_error":false,"num_turns":16,"stop_reason":null,"session_id":"1a0c7f24-b0a7-44cf-b3f6-292eabe7ac28","total_cost_usd":0.19146629999999998,"usage":{"input_tokens":19,"cache_creation_input_tokens":55778,"cache_read_input_tokens":671738,"output_tokens":5302,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":55778,"ephemera
**Files modified:** apps/webapp/src/webapp/api/v1/ws.py, apps/webapp/src/webapp/adapters/persistence/models/shootout.py, apps/webapp/src/webapp/api/pages.py, apps/webapp/src/webapp/api/v1/jobs.py, apps/webapp/src/webapp/main.py, apps/worker/src/worker/jobs/audio.py, apps/worker/src/worker/jobs/shootout.py, apps/worker/src/worker/jobs/master_audio.py, frontend/astro/src/pages/fragments/shootouts/detail.html.ts, frontend/astro/src/pages/layouts/base.astro, frontend/astro/src/pages/jobs/index.astro, infrastructure/nginx/nginx.conf.template
**JSONL excerpt:** {"event": "validation_fail", "story_id": "02-processing-and-progress", "attempt": 1, "check_type": "http+dom", "failure_category": "implementation", "failure_reason": "Agent reported overall status as fail", "evidence": "Agent reported overall status as fail\n{\"type\":\"result\",\"subtype\":\"error_max_turns\",\"duration_ms\":58002,\"duration_api_ms\":62302,\"is_error\":false,\"num_turns\":16,\"stop_reason\":null,\"session_id\":\"1a0c7f24-b0a7-44cf-b3f6-292eabe7ac28\",\"total_cost_usd\":0.19146629999999998,\"usage\":{\"input_tokens\":19,\"cache"}
