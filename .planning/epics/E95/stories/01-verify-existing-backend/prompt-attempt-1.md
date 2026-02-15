[GTS]|rules:{authentication,conversation-ux,error-ownership,github,no-defensive-parsing,no-workarounds,query-patterns,security,wait-for-instructions}|skills:{gts-architecture,gts-backend-dev}|wiki:{api-design,design-patterns}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 01-verify-existing-backend
**Name:** Verify and fix existing backend services
**Purpose:** Verify that all existing backend services (DI tracks, IR upload, asset service, tags, presets, block types, groups, comments, notifications, audit, exception handlers, shutdown) are properly wired in main.py, respond to API requests, and have correct schema validation. Fix any integration issues found.

### Scope
**Modify:**
- `apps/webapp/src/webapp/main.py`
- `apps/webapp/src/webapp/api/v1/html.py`
- `apps/webapp/src/webapp/api/v1/di_tracks.py`
- `apps/webapp/src/webapp/api/v1/shootouts.py`
- `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`

### Implementation Notes
- Verify ALL routers are mounted in main.py and exception handlers are registered
- Verify DI track upload endpoint accepts correct field names (name, pickup, guitar) and returns waveform data
- Verify signal_chain_groups router is reachable and CRUD + generate_permutations works
- Verify shootout comments CRUD endpoints work end-to-end
- Verify tags, presets, block_types, notifications, files endpoints respond correctly
- Verify asset_service HMAC signing and file serving works
- Run just check to verify no import or type errors
- Fix any wiring issues found — do NOT add new features, only fix integration

### Validation Checkpoint

After this story, a **api+response** validation will verify:
- DI track upload endpoint accepts POST with file and metadata and returns 201 with track data including waveform (evidence: status_code, url, method, response_body_excerpt)
- Signal chain groups CRUD endpoints respond (list, create, get, update, delete, generate) at /api/v1/signal-chain-groups/ (evidence: status_code, url, method, response_body_excerpt)
- Tags API returns 200 on GET /api/v1/tags for authenticated user (evidence: status_code, url, method, response_body_excerpt)
- Block types API returns list of built-in types at GET /api/v1/block-types (evidence: status_code, url, method, response_body_excerpt)
- Exception handlers return JSON for API routes and HTML for page routes on errors (evidence: status_code, url, method, response_body_excerpt)
