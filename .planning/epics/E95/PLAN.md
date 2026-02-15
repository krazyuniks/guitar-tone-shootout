# Plan: Epic #95

## Goal

Complete all Phase 4 web application features so that DI track upload, signal chain groups, shootout wizard, content APIs, OAuth provider linking, and platform infrastructure all work end-to-end with passing quality gates.

## Observable Truths

1. A user can upload a DI track with metadata (name, guitar, pickup, notes), and the uploaded track appears in their library with waveform visualisation and audio metadata (duration, sample rate).
2. A user can browse public DI tracks on /di-tracks with pagination, and click through to a detail page showing waveform and metadata.
3. A user can upload a community IR file via the IR upload endpoint, and the resulting Gear + GearModel appear in the gear browse page with source='community'.
4. A user can serve/stream DI tracks and IR files via HMAC-signed URLs returned by the asset service, with ownership validation preventing access to other users' files.
5. A user can list their signal chain groups on the library page, create groups via the builder, and generate permutations (batch chain generation from N amps × M IRs).
6. A user can navigate the shootout creation wizard: step 1 selects chains (including from groups), step 2 selects a DI track, step 3 reviews and submits — creating a shootout with 2-20 chains and a required DI track.
7. A user can view a shootout detail page showing chains, DI track info, and processing status, and can post, view, and delete comments on that shootout.
8. A user can create, list, and delete tags via the Tags API, with tag names automatically lowercased and duplicates rejected.
9. A user can create, list, update, and delete presets via the Presets API, with chain parameter validation enforced by the PresetProcessor.
10. A user can list built-in block types via GET /api/v1/block-types, seeing categories and default parameter definitions.
11. A user can toggle gear models in/out of their library via the save/remove checkbox, and see model counts on gear cards.
12. Custom error pages render: visiting a non-existent URL shows the 404 page, and server errors show the 500 page, with JSON responses for API routes and HTML for page routes.
13. A user can visit /settings/account and see their connected OAuth providers and account details.
14. GET /sitemap.xml returns a valid XML sitemap including static pages, public shootouts, and gear pages.
15. Login via Google, GitHub, or Facebook OAuth redirects to the provider, completes the callback, and links the identity to the user's account.
16. The application handles graceful shutdown: returns 503 during drain period, waits for in-flight requests, and shuts down cleanly on SIGTERM/SIGINT.
17. Security-relevant events (login, CRUD operations) are recorded in the audit log and queryable.
18. Notifications API returns unread notifications for a user, and supports marking individual or all notifications as read.
19. just check, just test-regression, and just test-golden-path all pass.

## User Journeys

### Journey J1: Guitarist uploading and managing DI tracks

User logs in, navigates to Library > DI Tracks, uploads a WAV file with guitar and pickup metadata. The upload completes showing duration and waveform. User browses /di-tracks publicly and sees their track listed. User clicks the track to see the detail page with waveform visualisation. User streams the audio via the player which uses a signed URL.

**Truths covered:** 1, 2, 4
**Entry point:** /library/di-tracks
**Critical transitions:**
- /library/di-tracks -> Upload modal (Click upload button)
- Upload modal -> /library/di-tracks (Submit upload form, track appears in list)
- /library/di-tracks -> /di-tracks (Navigate to public browse)
- /di-tracks -> /di-tracks/{id} (Click track card)

### Journey J2: Guitarist building signal chains and creating shootouts

User navigates to Library > Chains, opens the builder, creates a signal chain group with multiple amps and IRs. Permutations are generated. User then starts shootout creation: selects chains from their library (including group-generated chains), picks a DI track, reviews the summary, and submits. The shootout detail page shows all chains and the DI track. User adds a comment on the shootout.

**Truths covered:** 5, 6, 7
**Entry point:** /library/chains
**Critical transitions:**
- /library/chains -> /library/chains/build (Click Build Chain button)
- /library/chains/build -> /library/chains (Save chain/group, return to list)
- /library/chains -> /shootout/create (Click Create Shootout)
- /shootout/create -> Step 2 (DI track selection) (Select chains, click Next)
- Step 2 -> Step 3 (Review) (Select DI track, click Next)
- Step 3 -> /shootout/{id} (Submit shootout)
- /shootout/{id} -> /shootout/{id} (Post comment, comment appears)

### Journey J3: Guitarist managing gear library and content

User browses /gear, clicks a gear item to see detail with license text and models. User toggles models into their library via checkboxes. User navigates to Library > My Gear and sees saved models with counts. User creates tags to organise their library. User uploads a community IR which appears as new gear. User lists block types to understand available processors.

**Truths covered:** 3, 8, 10, 11
**Entry point:** /gear
**Critical transitions:**
- /gear -> /gear/{slug} (Click gear card)
- /gear/{slug} -> /gear/{slug} (Toggle model save checkbox (HTMX))
- /gear/{slug} -> /library/my-gear (Navigate to library)
- /library/my-gear -> /library/my-gear (View saved models with counts)

### Journey J4: User managing account and platform features

User visits /settings/account and sees connected OAuth providers (T3K). User links their Google account via OAuth flow. The settings page now shows both T3K and Google as connected. User visits a non-existent page and sees custom 404. The sitemap.xml is accessible and contains gear and shootout URLs. Notifications show unread items which can be marked as read.

**Truths covered:** 12, 13, 14, 15, 17, 18
**Entry point:** /settings/account
**Critical transitions:**
- /settings/account -> Google OAuth (Click 'Connect Google' button)
- Google OAuth callback -> /settings/account (OAuth callback redirects back)
- /settings/account -> /nonexistent (Navigate to missing page)
- /nonexistent -> 404 page (Server returns custom 404)

### Journey J5: DevOps verifying platform infrastructure

The application starts cleanly with exception handlers registered. Sending SIGTERM triggers graceful shutdown: new requests get 503, in-flight requests complete, then the process exits. Presets API validates chain parameters. Quality gates (lint, types, tests) all pass.

**Truths covered:** 9, 16, 19
**Entry point:** /health
**Critical transitions:**
- /health -> /health (GET returns 200 with healthy status)
- Running state -> Draining state (SIGTERM signal)
- Draining state -> Shutdown (In-flight requests complete)

## Stories

### Story: Verify and fix existing backend services (`01-verify-existing-backend`)

**Purpose:** Verify that all existing backend services (DI tracks, IR upload, asset service, tags, presets, block types, groups, comments, notifications, audit, exception handlers, shutdown) are properly wired in main.py, respond to API requests, and have correct schema validation. Fix any integration issues found.

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, gts-architecture, service-patterns, error-handling]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Modify: `apps/webapp/src/webapp/main.py`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Modify: `apps/webapp/src/webapp/api/v1/di_tracks.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`

**Wiki Sections:** GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: design-patterns, GTS-Technical-Architecture :: domain-model

**Implementation Notes:**
- Verify ALL routers are mounted in main.py and exception handlers are registered
- Verify DI track upload endpoint accepts correct field names (name, pickup, guitar) and returns waveform data
- Verify signal_chain_groups router is reachable and CRUD + generate_permutations works
- Verify shootout comments CRUD endpoints work end-to-end
- Verify tags, presets, block_types, notifications, files endpoints respond correctly
- Verify asset_service HMAC signing and file serving works
- Run just check to verify no import or type errors
- Fix any wiring issues found — do NOT add new features, only fix integration

**Truths Addressed:** 1, 3, 4, 5, 7, 8, 9, 10, 11, 12, 16, 17, 18

---

### Validation Checkpoint: After Verify and fix existing backend services

**Type:** api+response
**Checks:**
- DI track upload endpoint accepts POST with file and metadata and returns 201 with track data including waveform (evidence: status_code, url, method, response_body_excerpt)
- Signal chain groups CRUD endpoints respond (list, create, get, update, delete, generate) at /api/v1/signal-chain-groups/ (evidence: status_code, url, method, response_body_excerpt)
- Tags API returns 200 on GET /api/v1/tags for authenticated user (evidence: status_code, url, method, response_body_excerpt)
- Block types API returns list of built-in types at GET /api/v1/block-types (evidence: status_code, url, method, response_body_excerpt)
- Exception handlers return JSON for API routes and HTML for page routes on errors (evidence: status_code, url, method, response_body_excerpt)

---

### Story: Verify and fix existing frontend pages and fragments (`02-verify-existing-frontend`)

**Purpose:** Verify that all SSR pages (DI tracks browse, library pages, shootout wizard, settings, gear detail) render correctly with proper HTMX fragment loading. Verify Astro templates build and dist/ is in sync. Fix any template or routing issues found.

**Agent:**
- model: sonnet
- skills: [gts-frontend-dev, htmx, astro-frontend]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 35
- max_budget_usd: 3.5

**Scope:**
- Modify: `frontend/astro/src/pages/pages/shootout_detail.html.ts`
- Modify: `frontend/astro/src/pages/pages/shootout_create.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/create/step1-chains.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/create/step2-ditrack.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/create/step3-review.html.ts`
- Modify: `apps/webapp/src/webapp/api/pages.py`

**Wiki Sections:** Frontend-Architecture :: template-architecture, Frontend-Architecture :: htmx-integration, Frontend-Architecture :: serving-architecture, Frontend-Architecture :: testability-requirements

**Implementation Notes:**
- Verify shootout wizard step 1 loads chains including group-generated chains
- Verify shootout wizard step 2 loads DI tracks with search/filter
- Verify shootout wizard step 3 shows review summary and submits correctly
- Verify shootout detail page loads comments fragment via HTMX
- Verify DI tracks browse page loads public_browse fragment
- Verify settings/account page renders with provider list
- Verify all HTMX fragments have correct hx-get/hx-post URLs matching backend routes
- Run just build-astro to verify templates compile
- Fix any template rendering or routing mismatches — do NOT redesign pages

**Truths Addressed:** 2, 6, 7, 13

---

### Validation Checkpoint: After Verify and fix existing frontend pages and fragments

**Type:** http+dom
**Checks:**
- Shootout create page at /shootout/create renders with wizard step 1 loading chains via HTMX (evidence: status_code, url, dom_selector, element_text)
- DI tracks browse page at /di-tracks renders and loads public browse fragment (evidence: status_code, url, dom_selector, element_text)
- Settings account page at /settings/account renders with provider list (evidence: status_code, url, dom_selector, element_text)
- Shootout detail page loads comments section via HTMX fragment (evidence: status_code, url, dom_selector, element_text)

---

### Story: Add Google, GitHub, and Facebook OAuth providers (`03-oauth-providers`)

**Purpose:** Implement OAuth provider classes for Google, GitHub, and Facebook following the T3K provider pattern. Wire them into the auth system so users can link multiple OAuth identities from the settings page.

**Agent:**
- model: sonnet
- skills: [gts-backend-dev, gts-auth, gts-architecture]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 35
- max_budget_usd: 3.5

**Scope:**
- Create: `apps/webapp/src/webapp/auth/providers/google.py`
- Create: `apps/webapp/src/webapp/auth/providers/github.py`
- Create: `apps/webapp/src/webapp/auth/providers/facebook.py`
- Modify: `apps/webapp/src/webapp/auth/providers/__init__.py`
- Modify: `apps/webapp/src/webapp/api/v1/auth.py`
- Modify: `apps/webapp/src/webapp/main.py`

**Wiki Sections:** GTS-Technical-Architecture :: auth, GTS-Technical-Architecture :: design-patterns

**Implementation Notes:**
- Study T3KProvider in apps/webapp/src/webapp/auth/providers/t3k.py for the interface pattern
- Each provider needs: build_authorization_url, exchange_code, get_user_info methods
- Provider configuration (client_id, client_secret, endpoints) via environment variables
- Replace the stub login_provider function in auth.py with actual provider dispatch
- Register providers in __init__.py and wire into the callback handler
- Providers must work with the existing IdentityService for multi-provider linking
- Use standard OAuth 2.0 Authorization Code flow for all three
- No provider-specific business logic in domain layer

**Truths Addressed:** 15

---

### Validation Checkpoint: After Add Google, GitHub, and Facebook OAuth providers

**Type:** api+response
**Checks:**
- GET /api/v1/auth/login/google returns 302 redirect to Google OAuth authorization URL (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/auth/login/github returns 302 redirect to GitHub OAuth authorization URL (evidence: status_code, url, method, response_body_excerpt)
- GET /api/v1/auth/login/facebook returns 302 redirect to Facebook OAuth authorization URL (evidence: status_code, url, method, response_body_excerpt)

---

### Story: End-to-end integration verification and quality gates (`04-integration-testing`)

**Purpose:** Run the full quality gate suite (lint, types, import contracts, regression tests, golden path tests) and fix any failures. Verify critical user journeys work by running existing E2E tests and adding any missing regression test coverage for new OAuth provider wiring.

**Agent:**
- model: sonnet
- skills: [gts-testing, gts-backend-dev, check]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: 40
- max_budget_usd: 4.0

**Scope:**
- Modify: `tests/regression/test_stack.py`

**Wiki Sections:** GTS-Technical-Architecture :: testing, REFERENCE-ARCHITECTURE :: testing-strategy

**Implementation Notes:**
- Run just check — fix any lint, type, or import contract errors
- Run just test-regression — fix any stack connectivity failures
- Run just test-golden-path — fix any E2E test failures
- If regression tests don't cover OAuth provider model/identity wiring, add minimal coverage
- Do NOT write new E2E tests for the full OAuth flow (requires real OAuth credentials)
- Add regression test for AuditLog and UserNotification ORM round-trips if missing
- Verify all API routers respond (200 or 401 for auth-required) — fix any 404/500 errors
- Final verification: just check && just test-regression && just test-golden-path must all pass

**Truths Addressed:** 19

---

### Validation Checkpoint: After End-to-end integration verification and quality gates

**Type:** regression
**Checks:**
- just check passes with zero errors (lint, types, import contracts) (evidence: test_command, exit_code, test_count, failure_count)
- just test-regression passes with all tests green (evidence: test_command, exit_code, test_count, failure_count)
- just test-golden-path passes with all E2E tests green (evidence: test_command, exit_code, test_count, failure_count)

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. A user can upload a DI track with metadata (name, guitar, pickup, notes), and the uploaded track appears in their library with waveform visualisation and audio metadata (duration, sample rate). | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 2. A user can browse public DI tracks on /di-tracks with pagination, and click through to a detail page showing waveform and metadata. | `frontend/astro/src/pages/pages/shootout_detail.html.ts`, `frontend/astro/src/pages/pages/shootout_create.html.ts`, `frontend/astro/src/pages/fragments/shootouts/comments.html.ts` (+4 more) | Verify and fix existing frontend pages and fragments |
| 3. A user can upload a community IR file via the IR upload endpoint, and the resulting Gear + GearModel appear in the gear browse page with source='community'. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 4. A user can serve/stream DI tracks and IR files via HMAC-signed URLs returned by the asset service, with ownership validation preventing access to other users' files. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 5. A user can list their signal chain groups on the library page, create groups via the builder, and generate permutations (batch chain generation from N amps × M IRs). | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 6. A user can navigate the shootout creation wizard: step 1 selects chains (including from groups), step 2 selects a DI track, step 3 reviews and submits — creating a shootout with 2-20 chains and a required DI track. | `frontend/astro/src/pages/pages/shootout_detail.html.ts`, `frontend/astro/src/pages/pages/shootout_create.html.ts`, `frontend/astro/src/pages/fragments/shootouts/comments.html.ts` (+4 more) | Verify and fix existing frontend pages and fragments |
| 7. A user can view a shootout detail page showing chains, DI track info, and processing status, and can post, view, and delete comments on that shootout. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+9 more) | Verify and fix existing backend services, Verify and fix existing frontend pages and fragments |
| 8. A user can create, list, and delete tags via the Tags API, with tag names automatically lowercased and duplicates rejected. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 9. A user can create, list, update, and delete presets via the Presets API, with chain parameter validation enforced by the PresetProcessor. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 10. A user can list built-in block types via GET /api/v1/block-types, seeing categories and default parameter definitions. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 11. A user can toggle gear models in/out of their library via the save/remove checkbox, and see model counts on gear cards. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 12. Custom error pages render: visiting a non-existent URL shows the 404 page, and server errors show the 500 page, with JSON responses for API routes and HTML for page routes. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 13. A user can visit /settings/account and see their connected OAuth providers and account details. | `frontend/astro/src/pages/pages/shootout_detail.html.ts`, `frontend/astro/src/pages/pages/shootout_create.html.ts`, `frontend/astro/src/pages/fragments/shootouts/comments.html.ts` (+4 more) | Verify and fix existing frontend pages and fragments |
| 14. GET /sitemap.xml returns a valid XML sitemap including static pages, public shootouts, and gear pages. |  |  |
| 15. Login via Google, GitHub, or Facebook OAuth redirects to the provider, completes the callback, and links the identity to the user's account. | `apps/webapp/src/webapp/auth/providers/google.py`, `apps/webapp/src/webapp/auth/providers/github.py`, `apps/webapp/src/webapp/auth/providers/facebook.py` (+3 more) | Add Google, GitHub, and Facebook OAuth providers |
| 16. The application handles graceful shutdown: returns 503 during drain period, waits for in-flight requests, and shuts down cleanly on SIGTERM/SIGINT. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 17. Security-relevant events (login, CRUD operations) are recorded in the audit log and queryable. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 18. Notifications API returns unread notifications for a user, and supports marking individual or all notifications as read. | `apps/webapp/src/webapp/main.py`, `apps/webapp/src/webapp/api/v1/html.py`, `apps/webapp/src/webapp/api/v1/di_tracks.py` (+2 more) | Verify and fix existing backend services |
| 19. just check, just test-regression, and just test-golden-path all pass. | `tests/regression/test_stack.py` | End-to-end integration verification and quality gates |
