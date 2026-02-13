# Plan: Phase 4 Completion — DI Tracks, Groups, Shootout Workflow, Content APIs, Platform Infra

## Goal

All Phase 4 web application features work end-to-end: DI track upload/browse/playback, signal chain group CRUD with permutation generation, shootout wizard creating shootouts, comments on shootouts, tag/preset/block-type APIs responding, custom error pages rendering, settings page showing providers, notification API functional, and all quality gates passing.

## Observable Truths

1. A user can upload a DI track with metadata (name, guitar, pickup) and see it listed in their library
2. A user can browse public DI tracks with pagination and see track details including waveform
3. A user can upload a community IR file and see it appear as gear in their library
4. A user can create, list, update, and delete signal chain groups via the API
5. A user can generate permutations from a signal chain group and receive chain IDs
6. A user can navigate the shootout creation wizard: select chains (step 1), select DI track (step 2), review and submit (step 3)
7. A user can view a shootout detail page showing chains, DI track info, and processing status
8. A user can post, view, and delete comments on a shootout
9. A user can create, list, and delete tags via the API with lowercase normalisation
10. A user can create, list, update, and delete presets via the API with parameter validation
11. A guest can list block types via the API (public, cached endpoint)
12. Visiting a non-existent page shows a styled 404 error page (not a raw JSON error)
13. A server error shows a styled 500 error page for page routes and JSON for API routes
14. A user can visit /settings/account and see their connected OAuth providers
15. A user can list, mark-read, and mark-all-read notifications via the API
16. The file serving endpoint streams files via HMAC-signed URLs with range support
17. All quality gates pass: `just check`, `just test-regression`, `just test-golden-path`

## User Journeys

### Journey 1: Authenticated User — DI Track Upload and Browse

An authenticated user navigates to their DI tracks library page at /library/di-tracks. The page loads and displays any existing tracks via HTMX fragment. The user clicks upload, fills in the metadata form (name, guitar, pickup), selects a WAV file, and submits. The track appears in the list with duration and waveform data. The user navigates to /di-tracks to see the public browse view. They click a track to view the detail page showing metadata and waveform visualisation.

**Truths covered:** 1, 2
**Entry point:** /library/di-tracks
**Critical transitions:**
- /library/di-tracks -> upload form (button click)
- upload form -> /library/di-tracks (form submit, HTMX refresh)
- /library/di-tracks -> /di-tracks (nav link)
- /di-tracks -> /di-tracks/{id} (list item click)

### Journey 2: Authenticated User — Shootout Creation Workflow

An authenticated user navigates to /shootout/create. Step 1 presents chain selection — the user selects chains from their library (individual chains and group chains are available). The user proceeds to step 2 where they select a DI track from their library via a search/filter modal. Step 3 shows a review of selected chains and DI track. The user submits and is redirected to the shootout detail page showing the chains, DI track, and processing status. The user adds a comment on the shootout.

**Truths covered:** 6, 7, 8
**Entry point:** /shootout/create
**Critical transitions:**
- /shootout/create step 1 -> step 2 (chain selection complete)
- step 2 -> step 3 (DI track selected)
- step 3 -> /shootout/{id} (form submit, redirect)
- /shootout/{id} -> comment added (HTMX POST)

### Journey 3: Authenticated User — Content APIs

An authenticated user interacts with the content APIs. They create a tag "crunch" via POST /api/v1/tags and see it normalised to lowercase. They list their tags and see the new tag. They create a preset for a signal chain block with parameter validation. They list and update the preset. They fetch block types from GET /api/v1/block-types (public endpoint, no auth required) and see the built-in processor definitions with parameter schemas.

**Truths covered:** 9, 10, 11
**Entry point:** /api/v1/tags
**Critical transitions:**
- POST /api/v1/tags -> tag created (201 response)
- GET /api/v1/tags -> tag list (200 response)
- POST /api/v1/presets -> preset created (201 response)
- GET /api/v1/block-types -> block type list (200 response, cached)

### Journey 4: Guest/Authenticated User — Error Pages, Platform, and Quality Gates

A guest visits a non-existent URL like /nonexistent and sees a styled 404 page with navigation back to home. An API client hits /api/v1/test/error/404 (dev mode) and receives a JSON error response. An authenticated user visits /settings/account and sees their T3K provider linked with Google/GitHub/Facebook shown as "coming soon". The user checks their notifications via GET /api/v1/notifications and marks one as read. Finally, all quality gates (`just check`, `just test-regression`, `just test-golden-path`) pass clean.

**Truths covered:** 12, 13, 14, 15, 17
**Entry point:** /nonexistent
**Critical transitions:**
- /nonexistent -> 404 page (nginx error_page)
- /api/v1/test/error/500 -> JSON 500 response (exception handler)
- / -> /settings/account (nav link)
- GET /api/v1/notifications -> notification list (200 response)
- just check -> all quality gates pass (CI-equivalent commands)

### Journey 5: Authenticated User — Signal Chain Groups and File Serving

An authenticated user creates a signal chain group via POST /api/v1/signal-chain-groups. They update the group to add gear options. They trigger permutation generation and receive created chain IDs. They upload a community IR via POST /api/v1/irs/upload and see a Gear entity created. They access a file via a signed URL at /api/v1/files/{signature} with range header support for audio streaming.

**Truths covered:** 3, 4, 5, 16
**Entry point:** /api/v1/signal-chain-groups
**Critical transitions:**
- POST /api/v1/signal-chain-groups -> group created (201 response)
- POST /api/v1/signal-chain-groups/{id}/generate -> chain IDs (200 response)
- POST /api/v1/irs/upload -> Gear + GearModel created (201 response)
- GET /api/v1/files/{sig} -> file streamed (200/206 response)

## Stories

### Story 1: Verification and Integration Wiring

**Purpose:** Verify all existing Phase 4 code compiles, imports correctly, and quality gates pass. Fix any import errors, missing dependencies, or broken wiring between services, repositories, and API routes.

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, gts-architecture, error-handling]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: []
- max_turns: 40
- max_budget_usd: 4.00

**Scope:**
- Create: (none expected)
- Modify: `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/pages.py`

**Implementation Notes:**
- Run `just check` (lint + types + import contracts) and fix all errors
- Run `just test-regression` and fix any failures
- Verify all routers are mounted in main.py and respond to requests
- Check that all services, repositories, and models import correctly
- Fix any circular import issues or missing schema definitions
- Do NOT add new features — only fix broken wiring in existing code

**Truths Addressed:** 17

---

### Validation Checkpoint: After Verification and Integration Wiring

**Type:** quality
**Checks:**
- `just check` passes with zero errors (evidence: commands_run, exit_code, error_count)
- `just test-regression` passes (evidence: test_command, exit_code, test_count, failure_count)

---

### Story 2: API Endpoint Smoke Tests

**Purpose:** Verify all Phase 4 API endpoints respond correctly by running the E2E test suite. Fix any endpoint-level issues (wrong status codes, missing validations, broken template rendering).

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, gts-testing, web-handlers]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: []
- max_turns: 40
- max_budget_usd: 4.00

**Scope:**
- Create: (none expected)
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py`, `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/pages.py`

**Implementation Notes:**
- Run `just test-golden-path` and analyse failures
- Fix endpoint-level bugs: wrong status codes, missing template variables, broken HTMX fragment responses
- Verify shootout create wizard steps work end-to-end
- Verify comments HTMX fragment loads on shootout detail page
- Verify settings/account page renders with provider status
- Verify 404/500 error pages render via nginx and FastAPI
- Do NOT refactor — fix only what is broken

**Truths Addressed:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16

---

### Validation Checkpoint: After API Endpoint Smoke Tests

**Type:** regression
**Checks:**
- `just test-golden-path` passes (evidence: test_command, exit_code, test_count, failure_count)
- `just test-regression` still passes (evidence: test_command, exit_code, test_count, failure_count)

---

### Story 3: Regression Test Coverage

**Purpose:** Write regression tests that verify the key Phase 4 features work as ORM round-trips, serving as a safety net against future regressions.

**Agent:**
- model: sonnet
- skills: [gts-testing, gts-backend-dev]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: []
- max_turns: 35
- max_budget_usd: 3.50

**Scope:**
- Create: `tests/regression/test_phase4_completion.py`
- Modify: `tests/regression/conftest.py`

**Implementation Notes:**
- Add regression tests for Phase 4 entities: ShootoutComment, Tag, Preset, UserNotification, AuditLog
- Test ORM model round-trips (create, save, retrieve) for each entity
- Test repository operations where repositories exist
- Use in-memory SQLite like existing regression tests in test_stack.py
- Follow patterns in existing test_stack.py
- Run `just test-regression` to verify all pass

**Truths Addressed:** 8, 9, 10, 15, 17

---

### Validation Checkpoint: After Regression Test Coverage

**Type:** regression
**Checks:**
- `just test-regression` passes including new Phase 4 tests (evidence: test_command, exit_code, test_count, failure_count)
- `just check` still passes (evidence: commands_run, exit_code, error_count)

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1 | di_tracks.py, di_track_service.py, library/di-tracks.html | Story 2 |
| 2 | pages.py (di-tracks route), fragments/di-tracks/ | Story 2 |
| 3 | irs.py, ir_upload_service.py | Story 2 |
| 4 | signal_chain_groups.py, signal_chain_group_service.py | Story 2 |
| 5 | signal_chain_groups.py (generate endpoint) | Story 2 |
| 6 | html.py (shootout-create fragments), pages.py (create route) | Story 2 |
| 7 | pages.py (shootout detail route), fragments/shootouts/ | Story 2 |
| 8 | shootouts.py (comment endpoints), shootout_comment_service.py | Story 2, 3 |
| 9 | tags.py, tag_service.py | Story 2, 3 |
| 10 | presets.py, preset_service.py, preset_processor.py | Story 2, 3 |
| 11 | block_types.py, block_type_registry.py | Story 2 |
| 12 | 404.astro, exception_handlers.py, nginx.conf.template | Story 2 |
| 13 | 500.astro, exception_handlers.py | Story 2 |
| 14 | pages.py (settings/account), settings_account.html | Story 2 |
| 15 | notifications.py, notification_service.py | Story 2, 3 |
| 16 | files.py, asset_service.py | Story 2 |
| 17 | All quality gate commands | Story 1, 3 |
