# Curation: Epic #146

## Candidate Journeys

### Group detail page navigation (`CJ1`)

**Entry point:** Group list page link click (`/library/chains/group?id=<uuid>`)
**Desired outcome:** User sees group detail page with name, description, and chain list
**Key steps:**
- Click group item link on group list page
- SSR page handler resolves group by ID with user ownership check
- Jinja2 template renders group detail using existing `group_detail.html` fragment
- Page displays group info and associated chains

### Shootout creation ownership guard (`CJ2`)

**Entry point:** POST `/shootout/create` with chain_ids
**Desired outcome:** Shootout creation rejects chains not owned by current user (404)
**Key steps:**
- User submits shootout creation form with selected chains
- Handler validates each chain's user_id matches current_user.id
- Non-owned chain returns 404
- Owned chains proceed to create shootout as before

### Comment editing flow (`CJ3`)

**Entry point:** Shootout detail page, edit button on own comment
**Desired outcome:** Comment updated inline via HTMX swap
**Key steps:**
- Author sees edit button on their comment (non-authors do not)
- Click edit shows inline form with current comment text
- Submit sends PATCH to `/api/v1/shootouts/{id}/comments/{comment_id}`
- Updated comment replaces form via HTMX swap
- Non-author PATCH returns 404

### is_system_track cleanup (`CJ4`)

**Entry point:** DI track page render
**Desired outcome:** No is_system_track references remain; pages render correctly
**Key steps:**
- Remove hardcoded `is_system_track: False` from context.py
- Remove is_system_track badge and conditional delete-button logic from track_item.html
- Rebuild Astro (committed dist)
- Verify DI track pages render without errors

## Story Slices

### Shootout chain ownership validation (`SL1`)

Add user_id ownership check for all chain_ids and di_track_id in shootout creation handler; return 404 on mismatch

**Likely surfaces:**
- apps/webapp/src/webapp/api/pages/shootouts.py

### Group detail page endpoint (`SL2`)

Add SSR page handler for GET /library/chains/group that loads group by ID (with user ownership) and renders the existing group_detail.html Jinja2 fragment

**Likely surfaces:**
- apps/webapp/src/webapp/api/pages/chains.py
- apps/webapp/src/webapp/api/pages/__init__.py
- frontend/astro/src/pages/fragments/library/group_detail.html.ts

### Comment edit API + frontend (`SL3`)

Add PATCH endpoint for comment editing with author ownership check, plus HTMX inline edit UI on shootout detail page

**Likely surfaces:**
- apps/webapp/src/webapp/api/v1/shootouts.py
- apps/webapp/src/webapp/adapters/persistence/models/shootout_comment.py
- apps/webapp/src/webapp/api/pages/context.py
- frontend/astro/src/pages/fragments/library/group_detail.html.ts

### Remove is_system_track dead code (`SL4`)

Remove hardcoded is_system_track from context.py, remove badge and conditional logic from track_item.html, rebuild Astro dist

**Likely surfaces:**
- apps/webapp/src/webapp/api/pages/context.py
- frontend/astro/src/pages/fragments/library/track_item.html
- frontend/astro/dist/fragments/library/track_item.html

## Missing Assumptions

- **Assumption:** Comment PATCH route path: epic says `/api/v1/comments/<id>` but existing comment endpoints are nested under `/api/v1/shootouts/{shootout_id}/comments/{comment_id}`
  **Why it matters:** Route structure affects frontend HTMX targets and API consistency. Nested route requires shootout_id; flat route does not.
  **Planner action:** Follow existing nested convention (`/api/v1/shootouts/{shootout_id}/comments/{comment_id}`) unless epic owner explicitly overrides
- **Assumption:** Group detail page handler location: could be a new route in chains.py or a new file
  **Why it matters:** chains.py already handles chain list pages; adding group detail there follows existing patterns but the group_detail template references group-specific data (slots, permutations, generate button) not covered by the epic's observable outcomes
  **Planner action:** Scope the group detail page to the epic's stated outcomes only (name, description, chain list). The existing template has additional features (slots, generate button) — render what the template needs but only test what the epic specifies.
- **Assumption:** DI track ownership validation in shootout creation: epic mentions chain ownership but the handler also accepts di_track_id without ownership check
  **Why it matters:** Same security gap applies to DI tracks — a user could reference another user's DI track
  **Planner action:** Include di_track_id ownership validation alongside chain_ids validation in the same story
- **Assumption:** Comment body field name: epic says `body` but the ShootoutComment model uses `content`
  **Why it matters:** API schema field name must match either model field or a mapped alias. Using `body` in the API while the model uses `content` requires a Pydantic alias or rename.
  **Planner action:** Use model's actual field name `content` in the PATCH schema, or add a Pydantic alias if `body` is preferred in the API contract

## Scope Tensions

- **Tension:** Group detail template has more features than epic outcomes specify
  **Tradeoff:** The existing group_detail.html.ts template includes slot configuration, generate button, and delete button — but the epic only requires name, description, and chain list. Wiring all template features requires additional backend work not scoped by the epic.
  **Planner guidance:** Wire the full template since it already exists, but only write regression tests for the epic's stated observable outcomes (name, description, chain list). Don't create new backend features to support template buttons that already have API endpoints.
- **Tension:** Astro dist is committed — frontend changes require build step
  **Tradeoff:** Modifying track_item.html.ts and any comment templates requires `just build-astro` and committing the dist output. This creates large diffs but is the established pattern.
  **Planner guidance:** Group all frontend template changes together where possible to minimise build cycles. Ensure each story that touches Astro sources includes the dist rebuild.

## Planner Handoff

**Recommended story shape:** Four independent stories matching the four feature areas: security fix (SL1), group detail page (SL2), comment editing (SL3), dead code cleanup (SL4). Each is independently shippable. SL1 is highest priority (security). SL4 is lowest risk and can go last.

**Priority order:**
- SL1: Shootout chain ownership — security fix, ship first
- SL2: Group detail page — wires existing template to missing handler
- SL3: Comment editing — new API endpoint + HTMX frontend
- SL4: is_system_track cleanup — pure deletion, lowest risk

**Watchouts:**
- Comment endpoints are NESTED under shootouts (`/shootouts/{id}/comments/{cid}`), not flat as epic text implies — planner must use nested routes
- ShootoutComment model field is `content` not `body` — API schema must reconcile
- group_detail.html.ts template already exists with full UI — the handler just needs to load the right data and render it, not build a new template
- Astro dist is committed — any template changes need `just build-astro` + commit dist files
- Do NOT edit .gemini/ config files or scripts/epic_ingest.py — those are unrelated to this epic despite appearing in repo_facts likely_edit_targets
