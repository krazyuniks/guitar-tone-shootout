# Plan: Epic #146

## Goal

Address high-priority security gap (shootout chain ownership validation), wire the missing group detail page endpoint, add comment editing, and remove dead is_system_track references.

## Observable Truths

1. GET /library/chains/group?id=<uuid> returns the group detail page showing group name, description, and list of chains in the group
2. Clicking a group item link on the group list page navigates to the group detail page (no 404)
3. Creating a shootout with a signal chain not owned by the current user returns 404 (not 403, not success)
4. Creating a shootout with a chain owned by the current user succeeds as before
5. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated text"} updates the comment; returns updated comment
6. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author returns 404
7. Comment on shootout detail page shows an edit button for the author only
8. Clicking edit shows an inline form; submitting updates the comment text in place via HTMX
9. Hardcoded is_system_track: False removed from pages/context.py
10. Frontend is_system_track badge and delete-button suppression references removed from track_item.html, di-track detail, DITrackSelectModal, and api.ts

## User Journeys

### Journey J1: Authenticated user with signal chain groups

User visits their library and sees groups listed. They click a group item link which navigates to /library/chains/group?id=<uuid>. The group detail page renders showing the group name, description, and the chains belonging to that group.

**Truths covered:** 1, 2
**Entry point:** /library/chains
**Critical transitions:**
- Group list page (group_item.html fragment on library page) -> Group detail page at /library/chains/group?id=<uuid> (Standard <a href> link click from group_item.html template)

### Journey J2: Authenticated user creating a shootout

User navigates to the shootout creation wizard, selects chains and a DI track, and submits. If any selected chain or DI track is not owned by the user, the creation returns 404. If all are owned, the shootout is created and the user is redirected to the shootout detail page.

**Truths covered:** 3, 4
**Entry point:** /shootout/create
**Critical transitions:**
- Shootout creation wizard form -> 404 error (non-owned chain) or shootout detail page (owned chains) (POST /shootout/create form submission with HX-Redirect on success)

### Journey J3: Authenticated user editing their comment on a shootout

User visits a shootout detail page and sees comments. On their own comment, an edit button is visible. Clicking edit replaces the comment text with an inline form pre-filled with the current text. Submitting the form sends a PATCH to the API, and the updated comment replaces the form via HTMX swap. A non-author attempting to PATCH receives 404.

**Truths covered:** 5, 6, 7, 8
**Entry point:** /shootout/{shootout_id}
**Critical transitions:**
- Comment display with edit button (author only) -> Inline edit form with current comment text (Alpine.js toggle to show edit form)
- Inline edit form -> Updated comment displayed in place (HTMX PATCH to /api/shootouts/{id}/comments/{cid} with hx-swap)

### Journey J4: User viewing DI track pages

User views DI track library items and DI track detail pages. The is_system_track badge no longer appears. Delete buttons on library track items are no longer conditionally suppressed by is_system_track. Pages render correctly without errors.

**Truths covered:** 9, 10
**Entry point:** /library/tracks
**Critical transitions:**
- DI track library page with track_item.html fragments -> Track items render without is_system_track badge or conditional logic (SSR page render with cleaned template)

## Stories

### Story: Shootout chain ownership validation (`01-shootout-ownership`)

**Purpose:** Add user_id ownership checks for chain_ids and di_track_id in both shootout creation handlers (page form POST and REST API POST), returning 404 for non-owned resources.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-testing, gts-auth]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`

### Acceptance Criteria

- POST /shootout/create with a chain_id not owned by current_user returns 404
- POST /shootout/create with a di_track_id not owned by current_user returns 404
- POST /api/shootouts/ (REST API) with a di_track_id not owned by current_user returns 404
- POST /shootout/create with all owned chains and DI track succeeds as before (HX-Redirect to shootout detail)
- Ownership check queries SignalChain.user_id and DITrack.user_id against current_user.id
- 404 is returned (not 403) to avoid leaking resource existence, per AGENTS.md security rules

### Architectural Context

- apps/webapp/src/webapp/api/pages/shootouts.py: shootout_create_submit (line 335) — page form handler, uses get_current_user_required
- apps/webapp/src/webapp/api/v1/shootouts.py: create_shootout (line 121) — REST API handler, uses get_current_user (alias for required)
- Ownership check pattern already used in chain_detail_page (chains.py:119): `if not chain or chain.user_id != current_user.id: raise HTTPException(404)`
- SignalChain model has user_id field. DITrack model (webapp/adapters/persistence/models/di_track.py) has user_id field.
- The page handler extracts chain_ids from form.getlist and di_track_id from form.get — need to query DB for ownership of each

### Navigation Guide

- apps/webapp/src/webapp/api/pages/shootouts.py — shootout_create_submit at line 335
- apps/webapp/src/webapp/api/v1/shootouts.py — create_shootout at line 121
- apps/webapp/src/webapp/api/pages/chains.py:119 — ownership check pattern to follow
- apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py — SignalChain.user_id
- apps/webapp/src/webapp/adapters/persistence/models/di_track.py — DITrack.user_id

**Implementation Notes:**
- In page handler: after extracting chain_ids and di_track_id from form, query SignalChain and DITrack models to verify user_id == current_user.id for each
- In REST API: the create_shootout handler receives ShootoutCreateRequest with di_track_id — add ownership check before creating the Shootout entity
- REST API handler does not currently receive chain_ids in its request schema — only di_track_id needs ownership check there
- Use select() queries with .where(Model.id == id, Model.user_id == current_user.id) for efficient ownership checks
- Return 404 not 403 per security rules (don't leak existence)

**Truths Addressed:** 3, 4

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_signal_chain, make_di_track
**Assertions:**
- [http_status] route=POST /shootout/create, scenario=chain_id owned by different user, expected_status=404
- [http_status] route=POST /shootout/create, scenario=di_track_id owned by different user, expected_status=404
- [http_status] route=POST /shootout/create, scenario=all resources owned by current user, expected_status=200

---

### Validation Checkpoint: After Shootout chain ownership validation

**Type:** http
**Checks:**
- POST /shootout/create with a chain_id owned by a different user returns HTTP 404 (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootouts_pages.py -k ownership`]
- POST /shootout/create with all owned chains succeeds (returns 200 with HX-Redirect header) (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootouts_pages.py -k create`]

---

### Story: Group detail page endpoint (`02-group-detail-page`)

**Purpose:** Add SSR page handler for GET /library/chains/group that loads a signal chain group by ID with user ownership check and renders the existing group_detail.html Jinja2 template.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-testing, gts-frontend-dev]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/chains.py`
- Modify: `apps/webapp/src/webapp/api/pages/context.py`

### Acceptance Criteria

- GET /library/chains/group?id=<uuid> returns 200 with the group detail page for an owned group
- GET /library/chains/group?id=<uuid> returns 404 for a group not owned by the current user
- GET /library/chains/group?id=<non-existent-uuid> returns 404
- The rendered page shows group name, description, and chain list
- The page renders using the existing fragments/library/group_detail.html Jinja2 template
- Clicking a group item link on the group list page navigates to this page without 404

### Architectural Context

- chains.py already has routes for /library/chains and /chain/{chain_id} — add /library/chains/group here following the same pattern
- Group data comes from SignalChainGroupService.get_by_id() which returns a SignalChainGroup domain entity
- The group_detail.html template expects: group (id, name, description, base_chain, permutation_count) and slots (position, gear_count, gear_options, include_null)
- Existing group API (apps/webapp/src/webapp/api/v1/signal_chain_groups.py) shows the ownership pattern: `if not group or group.user_id != current_user.id: raise HTTPException(404)`
- Group item links already point to /library/chains/group?id={{ group.id }} (in group_item.html.ts:31)

### Navigation Guide

- apps/webapp/src/webapp/api/pages/chains.py — add new route handler here
- apps/webapp/src/webapp/services/signal_chain_group_service.py — SignalChainGroupService.get_by_id()
- frontend/astro/src/pages/fragments/library/group_detail.html.ts — template expects group and slots context
- frontend/astro/src/pages/fragments/library/group_item.html.ts:31 — link href pattern
- apps/webapp/src/webapp/api/v1/signal_chain_groups.py:116-160 — ownership check pattern
- apps/webapp/src/webapp/templates.py — templates.TemplateResponse usage

**Implementation Notes:**
- Add a group_to_detail_context() helper in context.py to map SignalChainGroup entity to template context dict
- Template expects group.base_chain (name string), group.permutation_count, and slots array with gear_options
- The base_chain needs to be resolved from base_chain_id to get the chain name — query SignalChain by base_chain_id
- Slots are derived from group.slot_positions and group.gear_options
- Use get_current_user_page dependency (redirects to login if not authenticated)
- Query parameter is `id` (not `group_id`) to match the existing links in group_item.html

**Truths Addressed:** 1, 2

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_signal_chain
**Assertions:**
- [http_status] route=GET /library/chains/group?id=<owned_group_id>, expected_status=200
- [dom_element] selector=[data-testid='group-detail'], description=Group detail container is present in response HTML
- [http_status] route=GET /library/chains/group?id=<other_user_group_id>, expected_status=404

---

### Validation Checkpoint: After Group detail page endpoint

**Type:** http+dom
**Checks:**
- GET /library/chains/group?id=<owned_group_id> returns 200 with group name and description in the HTML (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/ -k group_detail`]
- GET /library/chains/group?id=<other_user_id> returns 404 (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/ -k group_detail`]

---

### Story: Comment edit API endpoint (`03-comment-edit-api`)

**Purpose:** Add PATCH endpoint for updating comment content with author ownership check, plus service and repository update methods.

**Agent:**
- model: sonnet
- skills: [gts-architecture, gts-testing]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py`
- Modify: `apps/webapp/src/webapp/services/shootout_comment_service.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py`

### Acceptance Criteria

- PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated text"} updates the comment and returns CommentResponse with updated content
- PATCH by a non-author returns 404 (not 403), per AGENTS.md security rules
- PATCH with empty or whitespace-only content returns 422
- PATCH with content exceeding 2000 chars returns 422
- Existing comment create, list, and delete endpoints continue to work unchanged
- Contract decision: epic says PATCH /api/v1/comments/<id> with {"body": ...} but repo convention uses nested route /api/shootouts/{shootout_id}/comments/{comment_id} with field name 'content'. This story follows the repo convention (nested route, 'content' field) since all existing comment endpoints are nested and the model field is 'content'.

### Architectural Context

- Existing comment endpoints in apps/webapp/src/webapp/api/v1/shootouts.py are nested under /{shootout_id}/comments/
- ShootoutComment model field is 'content' (not 'body') — apps/webapp/src/webapp/adapters/persistence/models/shootout_comment.py
- Existing CommentCreateRequest uses 'content' field with min_length=1, max_length=2000
- Delete endpoint returns 404 for non-existent comments but 403 for non-authors — this story should return 404 for both (per AGENTS.md: return 404 not 403)
- Service layer pattern: ShootoutCommentService handles validation, repository handles persistence
- Repository get_by_id does NOT eagerly load user relationship — need to add joinedload for the update response

### Navigation Guide

- apps/webapp/src/webapp/api/v1/shootouts.py:519-567 — existing delete_comment endpoint pattern to follow
- apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py — CommentCreateRequest and CommentResponse schemas
- apps/webapp/src/webapp/services/shootout_comment_service.py — add update() method
- apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py — add update() method, fix get_by_id to optionally joinedload user

**Implementation Notes:**
- Add CommentUpdateRequest schema with content field (same validation as CommentCreateRequest)
- Add update() to ShootoutCommentRepository that sets content and flushes, then reloads with user relationship
- Add update() to ShootoutCommentService that checks ownership (comment.user_id == user_id) and delegates to repo
- Service update should raise ValueError if comment not found, and return 404 in the API handler
- Service update should raise PermissionError if not author, but API handler should catch and return 404 (not 403) per security rules
- PATCH handler follows same structure as delete_comment: verify shootout, then update comment

**Truths Addressed:** 5, 6

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_shootout
**Assertions:**
- [api_response] method=PATCH, route=/api/shootouts/{shootout_id}/comments/{comment_id}, body={'content': 'updated text'}, expected_status=200, expected_field=content, expected_value=updated text
- [http_status] method=PATCH, route=/api/shootouts/{shootout_id}/comments/{comment_id}, scenario=non-author, expected_status=404
- [http_status] method=PATCH, route=/api/shootouts/{shootout_id}/comments/{comment_id}, body={'content': ''}, expected_status=422

---

### Validation Checkpoint: After Comment edit API endpoint

**Type:** api+response
**Checks:**
- PATCH /api/shootouts/{sid}/comments/{cid} by author returns 200 with updated content field (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_api.py -k edit`]
- PATCH /api/shootouts/{sid}/comments/{cid} by non-author returns 404 (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_api.py -k edit`]

---

### Story: Comment edit frontend (HTMX inline edit) (`04-comment-edit-frontend`)

**Purpose:** Add edit button (author-only) and inline edit form to the comments template, wired to the PATCH endpoint via HTMX.

**Agent:**
- model: sonnet
- skills: [gts-frontend-dev, gts-architecture, gts-testing]
- tools: []

**Scope:**
- Modify: `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`
- Modify: `frontend/astro/dist/fragments/shootouts/comments.html`
- Modify: `apps/webapp/src/webapp/api/pages/shootouts.py`

### Acceptance Criteria

- Comment items show an edit button (pencil icon) only when comment.is_own is true
- Edit button is adjacent to the existing delete button
- Clicking edit toggles an inline form (Alpine.js) with a textarea pre-filled with the comment text
- Submitting the inline form sends HTMX PATCH to /api/shootouts/{shootout_id}/comments/{comment_id} with content field
- On success, the updated comment replaces the form via HTMX swap
- Edit button and form have data-testid attributes: comment-edit, comment-edit-form, comment-edit-textarea, comment-edit-submit
- Astro dist is rebuilt and committed

### Architectural Context

- Comments template: frontend/astro/src/pages/fragments/shootouts/comments.html.ts
- Template already uses is_own flag to show delete button (line 45-58)
- Comments are loaded via HTMX: hx-get=/shootout/{id}/comments from the shootout detail page
- The shootout_comments_fragment handler in pages/shootouts.py (line 403) renders the comments template
- HTMX PATCH needs to target the comment item and swap the updated content
- The PATCH endpoint returns JSON (CommentResponse) — the frontend needs an HTMX fragment endpoint or use hx-swap with an Alpine.js approach
- Pattern: use Alpine.js for toggle state (edit mode on/off), HTMX for the actual PATCH + swap

### Navigation Guide

- frontend/astro/src/pages/fragments/shootouts/comments.html.ts — full template file
- frontend/astro/dist/fragments/shootouts/comments.html — compiled dist to update
- apps/webapp/src/webapp/api/pages/shootouts.py:403 — shootout_comments_fragment handler
- The comment form currently uses hx-post and hx-target='[data-testid=comments-list]' — follow similar patterns
- just build-astro to rebuild dist after template changes

**Implementation Notes:**
- Add an HTMX fragment endpoint for comment edit that returns the single updated comment HTML (not JSON), following the same pattern as the comments list fragment
- The PATCH should target the individual comment-item div and replace it with the updated comment
- Use Alpine.js x-data for edit mode toggle: x-data="{editing: false}" on the comment item
- When editing=true, show textarea + save/cancel buttons; when false, show comment text + edit/delete buttons
- The HTMX PATCH target should be closest [data-testid='comment-item'] with hx-swap='outerHTML'
- After build-astro, commit both src and dist changes

**Truths Addressed:** 7, 8

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_shootout
**Assertions:**
- [dom_element] selector=[data-testid='comment-edit'], description=Edit button present on own comments
- [dom_absent] selector=[data-testid='comment-edit'], description=Edit button absent on other users' comments

---

### Validation Checkpoint: After Comment edit frontend (HTMX inline edit)

**Type:** http+dom
**Checks:**
- Comment HTML fragment for own comments contains edit button with data-testid='comment-edit' (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k edit`]
- Comment HTML fragment for other users' comments does not contain edit button (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k edit`]

---

### Story: Remove is_system_track dead code (`05-remove-is-system-track`)

**Purpose:** Remove all is_system_track references from backend context mapper, frontend templates, TypeScript types, and React components. Rebuild Astro dist.

**Agent:**
- model: sonnet
- skills: [gts-frontend-dev, gts-architecture]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/context.py`
- Modify: `frontend/astro/src/pages/fragments/library/track_item.html.ts`
- Modify: `frontend/astro/dist/fragments/library/track_item.html`
- Modify: `frontend/astro/src/pages/pages/di-tracks/detail.html.ts`
- Modify: `frontend/astro/dist/pages/di-tracks/detail.html`
- Modify: `frontend/astro/src/lib/api.ts`
- Modify: `frontend/astro/src/components/SignalChain/DITrackSelectModal.tsx`

### Acceptance Criteria

- Hardcoded 'is_system_track': False removed from di_track_to_library_context() in context.py
- is_system_track badge conditional removed from track_item.html.ts (line 86-88)
- is_system_track conditional on delete button suppression removed from track_item.html.ts (line 95) — the delete/toggle buttons should always show in library view
- is_system_track badge conditional removed from di-tracks/detail.html.ts
- is_system_track field removed from TypeScript interfaces in api.ts
- is_system_track badge rendering removed from DITrackSelectModal.tsx
- Astro dist is rebuilt and committed
- DI track library pages and detail pages render without errors after removal

### Architectural Context

- context.py line 108: 'is_system_track': False — hardcoded, never True
- track_item.html.ts lines 86-88: {% if track.is_system_track %} badge
- track_item.html.ts line 95: {% if is_library_view and not track.is_system_track %} — gate on action buttons
- di-tracks/detail.html.ts line 66: {% if track.is_system_track %} badge
- api.ts lines 489, 505: is_system_track: boolean in TypeScript interfaces
- DITrackSelectModal.tsx line 229: {track.is_system_track && (...)} badge rendering
- Since is_system_track is always False, removing it changes no visible behaviour

### Navigation Guide

- apps/webapp/src/webapp/api/pages/context.py:108 — hardcoded False
- frontend/astro/src/pages/fragments/library/track_item.html.ts:86-95 — two conditionals to remove
- frontend/astro/src/pages/pages/di-tracks/detail.html.ts:66 — badge conditional
- frontend/astro/src/lib/api.ts:489,505 — TypeScript interface fields
- frontend/astro/src/components/SignalChain/DITrackSelectModal.tsx:229 — React badge rendering
- just build-astro to rebuild dist

**Implementation Notes:**
- In context.py: simply remove the 'is_system_track': False line from di_track_to_library_context()
- In track_item.html.ts: remove the {% if track.is_system_track %} badge block (3 lines). For the action buttons, change {% if is_library_view and not track.is_system_track %} to just {% if is_library_view %}
- In detail.html.ts: remove the {% if track.is_system_track %} badge block
- In api.ts: remove is_system_track field from both interfaces
- In DITrackSelectModal.tsx: remove the {track.is_system_track && (...)} JSX block and its comment
- Run just build-astro after all template changes, then commit both src and dist

**Truths Addressed:** 9, 10

### Test Spec

**Type:** integration
**Assertions:**
- [dom_absent] description=No is_system_track references in rendered DI track pages

---

### Validation Checkpoint: After Remove is_system_track dead code

**Type:** process
**Checks:**
- No is_system_track references remain in backend context.py (evidence: command, exit_code, output_tail) [cmd: `grep -r 'is_system_track' apps/webapp/src/webapp/api/pages/context.py; test $? -eq 1`]
- No is_system_track conditionals remain in Astro src templates (evidence: command, exit_code, output_tail) [cmd: `grep -r 'is_system_track' frontend/astro/src/pages/fragments/library/track_item.html.ts frontend/astro/src/pages/pages/di-tracks/detail.html.ts; test $? -eq 1`]
- Golden path tests pass after all changes (evidence: command, exit_code, output_tail) [cmd: `just test-golden-path`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. GET /library/chains/group?id=<uuid> returns the group detail page showing group name, description, and list of chains in the group | `apps/webapp/src/webapp/api/pages/chains.py`, `apps/webapp/src/webapp/api/pages/context.py` | Group detail page endpoint |
| 2. Clicking a group item link on the group list page navigates to the group detail page (no 404) | `apps/webapp/src/webapp/api/pages/chains.py`, `apps/webapp/src/webapp/api/pages/context.py` | Group detail page endpoint |
| 3. Creating a shootout with a signal chain not owned by the current user returns 404 (not 403, not success) | `apps/webapp/src/webapp/api/pages/shootouts.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` | Shootout chain ownership validation |
| 4. Creating a shootout with a chain owned by the current user succeeds as before | `apps/webapp/src/webapp/api/pages/shootouts.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` | Shootout chain ownership validation |
| 5. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated text"} updates the comment; returns updated comment | `apps/webapp/src/webapp/api/v1/shootouts.py`, `apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py`, `apps/webapp/src/webapp/services/shootout_comment_service.py` (+1 more) | Comment edit API endpoint |
| 6. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author returns 404 | `apps/webapp/src/webapp/api/v1/shootouts.py`, `apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py`, `apps/webapp/src/webapp/services/shootout_comment_service.py` (+1 more) | Comment edit API endpoint |
| 7. Comment on shootout detail page shows an edit button for the author only | `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`, `frontend/astro/dist/fragments/shootouts/comments.html`, `apps/webapp/src/webapp/api/pages/shootouts.py` | Comment edit frontend (HTMX inline edit) |
| 8. Clicking edit shows an inline form; submitting updates the comment text in place via HTMX | `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`, `frontend/astro/dist/fragments/shootouts/comments.html`, `apps/webapp/src/webapp/api/pages/shootouts.py` | Comment edit frontend (HTMX inline edit) |
| 9. Hardcoded is_system_track: False removed from pages/context.py | `apps/webapp/src/webapp/api/pages/context.py`, `frontend/astro/src/pages/fragments/library/track_item.html.ts`, `frontend/astro/dist/fragments/library/track_item.html` (+4 more) | Remove is_system_track dead code |
| 10. Frontend is_system_track badge and delete-button suppression references removed from track_item.html, di-track detail, DITrackSelectModal, and api.ts | `apps/webapp/src/webapp/api/pages/context.py`, `frontend/astro/src/pages/fragments/library/track_item.html.ts`, `frontend/astro/dist/fragments/library/track_item.html` (+4 more) | Remove is_system_track dead code |
