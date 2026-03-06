# Plan: Epic #146

## Goal

Users can view group detail pages, edit their own comments inline, and are prevented from creating shootouts with chains they don't own; dead is_system_track code is removed.

## Observable Truths

1. GET /library/chains/group?id=<uuid> returns the group detail page showing group name, description, and list of chains in the group
2. Clicking a group item link on the group list page navigates to the group detail page (no 404)
3. Creating a shootout with a signal chain not owned by the current user returns 404
4. Creating a shootout with a chain owned by the current user succeeds as before
5. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated text"} updates the comment body and returns the updated comment. EPIC CONTRACT OVERRIDE: the epic originally specified PATCH /api/v1/comments/<id> with {"body": str}, but locked user decisions decision-api-1 (nested routes under shootout resource) and decision-api-3 (field named 'content' matching DB column and existing CommentCreateRequest) mandate this shape instead. This is the authoritative contract.
6. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author returns 404
7. Comment on shootout detail page shows an edit button for the author only
8. Clicking edit shows an inline form; submitting updates the comment text in place via HTMX
9. Hardcoded is_system_track: False removed from pages/context.py
10. Frontend is_system_track badge and delete-button suppression references removed

## User Journeys

### Journey J1: Authenticated user with signal chain groups

User navigates to their chain library, sees a list of groups, clicks on one, and lands on the group detail page showing the group name, description, slot configuration, and action buttons.

**Truths covered:** 1, 2
**Entry point:** /library/chains
**Critical transitions:**
- /library/chains -> /library/chains/group?id=<uuid> (Click group item link)
- /library/chains/group?id=<uuid> -> Group detail content rendered (SSR page loads with group context)

### Journey J2: Authenticated user creating a shootout

User goes through the shootout creation wizard, selects chains and a DI track, and submits. If all chains are owned by the user, the shootout is created and user is redirected to the detail page. If a chain is not owned (e.g. manipulated form data), the server returns 404.

**Truths covered:** 3, 4
**Entry point:** /shootout/create
**Critical transitions:**
- /shootout/create -> POST /shootout/create (Form submission with chain_ids — form action and hidden inputs wired on the create page)
- POST /shootout/create -> /shootout/<id> (HX-Redirect on success (owned chains))
- POST /shootout/create -> 404 response (Server rejects unowned chain_ids)

### Journey J3: Authenticated user editing and managing comments

User views a shootout detail page with comments. The page contains an HTMX hx-get that loads the comments fragment. They see an edit button next to their own comments but not others'. Clicking edit (Alpine.js toggle) swaps the comment text for an inline form. They change the text and submit, and the comment updates in place via HTMX hx-patch. The updated_at timestamp is reflected. Attempting to edit another user's comment via the API returns 404. NOTE: the API endpoint is PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": str} per locked user decisions decision-api-1 and decision-api-3, overriding the epic's original /api/v1/comments/<id> + body contract.

**Truths covered:** 5, 6, 7, 8
**Entry point:** /shootout/{id}
**Critical transitions:**
- Shootout detail page -> Comments section loaded (HTMX hx-get targeting comments fragment endpoint on the shootout detail page)
- Comment display -> Inline edit form (Click edit button triggers Alpine.js x-on:click toggle showing edit form (x-show); integration tests verify markup+attributes, E2E tests verify interaction)
- Inline edit form -> Updated comment display (HTMX hx-patch on edit form submits to /shootout/{shootout_id}/comments/{comment_id} page handler which returns HTML fragment; hx-target and hx-swap control in-place replacement)

### Journey J4: User viewing DI tracks after cleanup

User browses their DI track library and views a track detail page. The is_system_track badge and delete suppression logic are gone — all tracks render cleanly without the dead field. Track list items contain links to detail pages that navigate correctly.

**Truths covered:** 9, 10
**Entry point:** /library/di-tracks
**Critical transitions:**
- /library/di-tracks -> Track list rendered (Page loads without is_system_track badges)
- Track list -> Track detail page (Click track item link (a[href] in track list item navigates to /library/di-tracks/<id>))

## Stories

### Story: Wire group detail page endpoint (`01-group-detail-page`)

**Purpose:** Add the SSR page handler and context mapper so the existing group_detail.html template is served at GET /library/chains/group?id=<uuid>

**Agent:**
- model: codex
- skills: [gts-frontend-dev, gts-architecture]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/chains.py`
- Modify: `apps/webapp/src/webapp/api/pages/context.py`

### Acceptance Criteria

- GET /library/chains/group?id=<valid-group-uuid> returns 200 with HTML containing the group name and description
- GET /library/chains/group?id=<other-users-group-uuid> returns 404
- GET /library/chains/group?id=<nonexistent-uuid> returns 404
- GET /library/chains/group without id param returns 422 or 404
- The rendered page contains data-testid='group-detail-page'
- The rendered page shows slot configuration with gear options
- GET /library/chains for a user with groups renders group items with working links to /library/chains/group?id=<uuid>

### Architectural Context

- Page handlers live in apps/webapp/src/webapp/api/pages/chains.py — follow the pattern of chain_detail_page() at line 108
- Context mappers live in apps/webapp/src/webapp/api/pages/context.py — follow the pattern of shootout_detail_context() at line 161
- The group detail template is at dist/fragments/library/group_detail.html — it expects context vars: group.id, group.name, group.description, group.base_chain, group.permutation_count, and a slots list
- SignalChainGroup ORM model at apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py:160 has user_id, name, description, base_chain_id, slot_positions, gear_options, include_null
- Ownership check pattern: if not group or group.user_id != current_user.id → raise HTTPException(404)

### Navigation Guide

- Page handler file: apps/webapp/src/webapp/api/pages/chains.py — add new route after line 169 (after chain_detail_page)
- Context mapper file: apps/webapp/src/webapp/api/pages/context.py — add group_to_detail_context after chain_to_library_context (line 134)
- Group ORM model: apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py:160 (SignalChainGroup class)
- Group repository: apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain_group_repository.py — get_by_id() at line 35
- Template expects: group dict (id, name, description, base_chain, permutation_count) + slots list (position, gear_count, gear_options[{name}], include_null)
- Group item links to: /library/chains/group?id={{ group.id }} (see frontend/astro/src/pages/fragments/library/group_item.html.ts:31)
- Group list page: apps/webapp/src/webapp/api/pages/chains.py — library_chains_page already renders group items with links

### Dependencies from Prior Stories


**Wiki Sections:** GTS-Technical-Architecture :: frontend, GTS-Technical-Architecture :: design-patterns, Frontend-Architecture

**Implementation Notes:**
- The group detail page needs a query param ?id=<uuid>, not a path param. Use request.query_params.get('id')
- The group_to_detail_context mapper needs to resolve gear names from gear_options UUIDs — query Gear table for names
- The template renders slots from group.slot_positions and group.gear_options. The context mapper needs to join these into a slots list
- base_chain needs to be resolved to a name via the base_chain_id FK relationship or a separate query
- permutation_count can be computed from len(gear_options) product, or use the domain entity's method if available
- Use the ORM model directly (not the domain entity) for the context mapper, following the same pattern as other context mappers

**Truths Addressed:** 1, 2

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_signal_chain, authenticated_client
**Assertions:**
- [http_status] method=GET, route=/library/chains/group?id={group.id}, auth=test_user, expected_status=200
- [dom_element] selector=[data-testid='group-detail-page'], expected_text=
- [http_status] method=GET, route=/library/chains/group?id=00000000-0000-0000-0000-000000000000, auth=test_user, expected_status=404
- [http_status] method=GET, route=/library/chains/group, auth=test_user, expected_status=422
- [dom_element] method=GET, route=/library/chains, auth=test_user, selector=a[href*='/library/chains/group?id='], context=group list page contains link to group detail

---

### Validation Checkpoint: After Wire group detail page endpoint

**Type:** http+dom
**Checks:**
- Group detail page renders for an owned group (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_group_detail_page.py -k test_group_detail_renders`]
- Group list page renders group items with links to group detail (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_group_detail_page.py -k test_group_list_contains_detail_link`]
- Group detail page returns 404 for non-owned group (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_group_detail_page.py -k test_group_detail_other_user_404`]

---

### Story: Validate chain ownership on shootout creation (`02-shootout-chain-ownership`)

**Purpose:** Prevent users from creating shootouts with signal chains they don't own by adding ownership validation to the shootout creation handler

**Agent:**
- model: codex
- skills: [gts-architecture, gts-security]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/shootouts.py`

### Acceptance Criteria

- GET /shootout/create renders the form page with chain selection fields (form wiring is present)
- POST /shootout/create with chain_ids owned by the current user creates the shootout and returns HX-Redirect to /shootout/<id>
- POST /shootout/create with any chain_id NOT owned by the current user returns 404
- POST /shootout/create with a nonexistent chain_id returns 404
- Following the HX-Redirect after successful creation renders the shootout detail page (200)

### Architectural Context

- Shootout creation handler: apps/webapp/src/webapp/api/pages/shootouts.py:335 (shootout_create_submit)
- SignalChain ORM model has user_id field: apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py:24
- Security rule: resource.user_id != current_user.id → return 404 (never 403)
- The handler already has the db session and current_user available
- chain_ids come from form data (line 350). Each must be validated against SignalChain.user_id

### Navigation Guide

- Handler: apps/webapp/src/webapp/api/pages/shootouts.py:335-400 (shootout_create_submit)
- SignalChain model import: from webapp.adapters.persistence.models.signal_chain import SignalChain
- Validation should go after the chain_ids length checks (after line 368) and before building ShootoutChainVO objects (line 370)
- Use: select(SignalChain).where(SignalChain.id.in_([UUID(cid) for cid in chain_ids]), SignalChain.user_id == current_user.id)
- Create page handler: apps/webapp/src/webapp/api/pages/shootouts.py — GET handler renders form with chain selection

### Dependencies from Prior Stories

- Story 01 added a group_detail_page route to chains.py and a group_to_detail_context mapper to context.py — no direct dependency but context.py has new code

**Wiki Sections:** GTS-Technical-Architecture :: auth, GTS-Technical-Architecture :: api-design

**Implementation Notes:**
- Query all submitted chain_ids in one query, filtering by user_id. If count of results != count of submitted chain_ids, at least one chain is unowned or missing → return 404
- Use sqlalchemy select with .where(SignalChain.id.in_(uuids), SignalChain.user_id == current_user.id)
- Return 404 with detail 'Chain not found' — generic message to avoid information leakage

**Truths Addressed:** 3, 4

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_signal_chain, make_di_track, authenticated_client
**Assertions:**
- [http_status] method=GET, route=/shootout/create, auth=test_user, expected_status=200, context=Create page renders with form
- [dom_element] method=GET, route=/shootout/create, auth=test_user, selector=form[action*='/shootout/create'], [hx-post*='/shootout/create'], context=Create page contains form wiring that submits to POST /shootout/create
- [http_status] method=POST, route=/shootout/create, auth=test_user, body={'name': 'Test', 'di_track_id': '{di_track.id}', 'chain_ids[]': ['{owned_chain.id}', '{owned_chain2.id}']}, expected_status=200, expected_header=HX-Redirect
- [http_status] method=GET, route={redirect_url_from_HX-Redirect}, auth=test_user, expected_status=200, context=Follow HX-Redirect to verify shootout detail page renders
- [dom_element] method=GET, route={redirect_url_from_HX-Redirect}, auth=test_user, selector=[data-testid='shootout-detail-page'], context=Redirect target is a valid shootout detail page
- [http_status] method=POST, route=/shootout/create, auth=test_user, body={'name': 'Test', 'di_track_id': '{di_track.id}', 'chain_ids[]': ['{owned_chain.id}', '{other_user_chain.id}']}, expected_status=404

---

### Validation Checkpoint: After Validate chain ownership on shootout creation

**Type:** http+dom
**Checks:**
- Shootout create page renders form with chain selection wiring (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_chain_ownership.py -k test_create_page_renders_form`]
- Shootout creation with unowned chain returns 404 (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_chain_ownership.py -k test_unowned_chain_returns_404`]
- Shootout creation with owned chains succeeds and returns HX-Redirect (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_chain_ownership.py -k test_owned_chains_success_with_redirect`]
- Redirect target page renders successfully after shootout creation (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_chain_ownership.py -k test_redirect_target_renders`]

---

### Story: Add comment edit API endpoint (`03-comment-edit-backend`)

**Purpose:** Add PATCH endpoint for editing comments, update service and repository with update method, add updated_at to response schema, and fix delete to return 404 instead of 403 for non-authors

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py`
- Modify: `apps/webapp/src/webapp/services/shootout_comment_service.py`
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py`

### Acceptance Criteria

- PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated"} by the author returns 200 with updated CommentResponse including updated_at
- PATCH /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author returns 404
- PATCH /api/shootouts/{shootout_id}/comments/{comment_id} for nonexistent comment returns 404
- DELETE /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author now returns 404 (was 403)
- CommentResponse schema includes updated_at field
- EPIC DEVIATION (authorized by locked user decisions): The epic originally specified PATCH /api/v1/comments/<id> with {"body": str}. Locked user decisions decision-api-1 (nested routes under shootout resource) and decision-api-3 (field named 'content' matching DB column and existing CommentCreateRequest) mandate PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": str} instead. The flat /api/v1/comments/<id> endpoint is intentionally NOT implemented. This deviation applies to both the edit endpoint and the non-author 404 behaviour, which are validated exclusively on the nested route.

### Architectural Context

- EPIC CONTRACT OVERRIDE: The epic originally specified PATCH /api/v1/comments/<id> with {"body": str}. Per locked user decisions decision-api-1 (nested routes under shootout resource) and decision-api-3 (field named 'content' matching DB column and existing CommentCreateRequest), this story implements PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": str} instead. This is intentional — the user decisions take precedence over the epic's original API shape. The verifier should treat this endpoint as the authoritative contract for comment editing.
- Repository pattern: apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py — add update() method following delete() pattern
- Service pattern: apps/webapp/src/webapp/services/shootout_comment_service.py — add update() following delete() pattern (lookup, ownership check, update)
- API route pattern: apps/webapp/src/webapp/api/v1/shootouts.py:519 (delete_comment) — add PATCH route following same structure
- Schema file: apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py — add CommentUpdateRequest and updated_at to CommentResponse
- Ownership rule: non-author gets 404, not 403. Fix existing delete_comment to use 404 instead of 403 (line 562-565)

### Navigation Guide

- Repository: apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py — add update() after delete() (line 109)
- Service: apps/webapp/src/webapp/services/shootout_comment_service.py — add update() after delete() (line 126). Raise ValueError for not-found AND non-author (both map to 404)
- API routes: apps/webapp/src/webapp/api/v1/shootouts.py — add PATCH route after delete_comment (line 567). Fix delete_comment PermissionError handler to return 404 (lines 562-565)
- Schemas: apps/webapp/src/webapp/api/v1/schemas/shootout_comment.py — add CommentUpdateRequest (same content validator as create), add updated_at: datetime | None to CommentResponse
- ORM model: apps/webapp/src/webapp/adapters/persistence/models/shootout_comment.py — already has updated_at via TimestampMixin

### Dependencies from Prior Stories

- Story 01 added group_to_detail_context to context.py — no direct dependency on comment work
- Story 02 added chain ownership validation to shootouts.py page handler — no overlap with v1/shootouts.py API routes

**Wiki Sections:** GTS-Technical-Architecture :: api-design, GTS-Technical-Architecture :: design-patterns

**Implementation Notes:**
- EPIC CONTRACT OVERRIDE: endpoint is PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": str}, NOT /api/v1/comments/<id> with {"body": str}. This follows locked user decisions decision-api-1 (nested routes) and decision-api-3 (content field). Do NOT change this to match the epic's original wording.
- The epic's original PATCH /api/v1/comments/<id> endpoint is intentionally NOT implemented. The nested route under the shootout resource is the sole implementation, per locked user decisions. Non-author 404 behaviour is validated on this nested route only.
- Service.update() should: get_by_id, check not None (ValueError), check user_id match (ValueError, NOT PermissionError — caller maps both to 404), strip+validate content, call repo.update(), return updated comment
- Repository.update() should: get_by_id, set content, flush, re-fetch with joinedload to return hydrated comment
- PATCH endpoint: verify shootout exists, call service.update(), catch ValueError → 404, return CommentResponse
- Delete endpoint fix: change PermissionError handler from 403 to 404, or better — change service.delete() to raise ValueError instead of PermissionError for ownership mismatch, making the API handler simpler
- CommentUpdateRequest: same as CommentCreateRequest (content field with strip+validate). Could even reuse CommentCreateRequest.

**Truths Addressed:** 5, 6

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_shootout(chains=2), authenticated_client
**Assertions:**
- [api_response] method=PATCH, route=/api/shootouts/{shootout.id}/comments/{comment.id}, auth=author_user, body={'content': 'updated text'}, expected_json={'content': 'updated text', 'updated_at': 'non-null'}
- [http_status] method=PATCH, route=/api/shootouts/{shootout.id}/comments/{comment.id}, auth=other_user, body={'content': 'hacked'}, expected_status=404
- [http_status] method=DELETE, route=/api/shootouts/{shootout.id}/comments/{comment.id}, auth=other_user, expected_status=404

---

### Validation Checkpoint: After Add comment edit API endpoint

**Type:** api+response
**Checks:**
- Comment edit PATCH by author returns updated comment with updated_at (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_api.py -k test_edit_comment_by_author`]
- Comment edit PATCH by non-author returns 404 (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_api.py -k test_edit_comment_non_author_returns_404`]
- Comment delete by non-author returns 404 (not 403) (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_api.py -k test_delete_non_author_returns_404`]

---

### Story: Add inline comment editing UI (`04-comment-edit-frontend`)

**Purpose:** Add edit button to comment template (visible for author only) and inline HTMX edit form that PATCHes the comment via a page handler (HTML fragment) and swaps the updated text in place

**Agent:**
- model: codex
- skills: [gts-frontend-dev]
- tools: []

**Scope:**
- Create: `frontend/astro/src/pages/fragments/shootouts/comment_edit_form.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`
- Modify: `apps/webapp/src/webapp/api/pages/shootouts.py`
- Modify: `apps/webapp/src/webapp/api/pages/context.py`

### Acceptance Criteria

- Each comment by the current user shows an edit button (data-testid='comment-edit') alongside the delete button
- Comments by other users do not show the edit button
- Clicking edit replaces the comment text with a textarea pre-filled with the current text and save/cancel buttons
- Submitting the edit form PATCHes /shootout/{shootout_id}/comments/{comment_id} (page handler) via HTMX and swaps the updated comment HTML fragment in place
- Cancelling the edit restores the original comment display
- Edited comments show '(edited)' indicator if updated_at differs from created_at
- The rendered comment HTML contains Alpine.js x-data for edit toggle state and a hidden edit form with textarea pre-filled with comment content
- The edit form has hx-patch attribute targeting the page handler endpoint for HTMX submission
- The shootout detail page contains an HTMX hx-get attribute that loads the comments fragment
- GET on the comments fragment endpoint returns 200 with rendered HTML containing comment content for a shootout with comments

### Architectural Context

- HTMX fragment pattern: comment template at frontend/astro/src/pages/fragments/shootouts/comments.html.ts
- Comment context mapper: apps/webapp/src/webapp/api/pages/context.py:229 (comment_to_context) — add updated_at field
- Two-endpoint chain: Story 03 created the JSON API PATCH at /api/shootouts/{id}/comments/{cid} in v1/shootouts.py. This story adds a page handler PATCH at /shootout/{id}/comments/{cid} in pages/shootouts.py that calls the same service.update() and returns an HTML fragment for HTMX swap.
- Alpine.js can handle the toggle between view/edit mode client-side without a server round-trip for the form display
- The page handler PATCH returns an HTML fragment (rendered Jinja2 template), NOT JSON. This is what HTMX swaps into the DOM.
- The shootout detail page must contain hx-get to load comments — verify this wiring exists (it should already be present; if not, add it)
- The comments fragment endpoint (hx-get target) must return rendered HTML with comment content — this is the J3 transition from 'Shootout detail page' to 'Comments section loaded'

### Navigation Guide

- Comment template: frontend/astro/src/pages/fragments/shootouts/comments.html.ts — edit button goes at line 45 alongside delete button
- Comment context mapper: apps/webapp/src/webapp/api/pages/context.py:229 — add updated_at to the dict
- Page handler: apps/webapp/src/webapp/api/pages/shootouts.py — add PATCH handler that calls service.update() and returns HTML fragment
- Build output must be committed: frontend/astro/dist/fragments/shootouts/ will need updating via just build-astro
- The page handler reuses ShootoutCommentService.update() from story 03 — same service, different response format (HTML vs JSON)
- Shootout detail template: frontend/astro/src/pages/pages/shootouts/detail.html.ts — verify hx-get for comments loading exists
- Comments fragment page handler: apps/webapp/src/webapp/api/pages/shootouts.py — the existing GET handler for comments fragment (verify it exists and returns rendered comment HTML)

### Dependencies from Prior Stories

- Story 03 created ShootoutCommentService.update() and ShootoutCommentRepository.update() — the page handler calls service.update()
- Story 03 added updated_at to CommentResponse schema — the page handler uses the same ORM field
- Story 03 added the JSON API PATCH at /api/shootouts/{shootout_id}/comments/{comment_id} — this story adds a parallel page handler PATCH at /shootout/{shootout_id}/comments/{comment_id} for HTML fragment response

**Wiki Sections:** Frontend-Architecture, GTS-Technical-Architecture :: frontend

**Implementation Notes:**
- Use Alpine.js x-data for edit state toggle rather than a server round-trip to show the form
- The edit form should use hx-patch targeting the page handler (/shootout/{id}/comments/{cid}), NOT the JSON API (/api/shootouts/{id}/comments/{cid}), so it returns an HTML fragment for HTMX swap
- Add a page handler: PATCH /shootout/{shootout_id}/comments/{comment_id} that calls service.update() and renders the updated comment as an HTML fragment using the comment template
- The comment_edit_form.html.ts template is a separate fragment for the edit form state of a single comment
- Add updated_at to comment_to_context() and show '(edited)' when updated_at > created_at + small delta
- The Astro dist/ files need to be rebuilt (just build-astro) and committed
- The comment HTML must include the edit form markup (textarea, save/cancel) controlled by Alpine.js x-show, so integration tests can verify the form structure exists in the rendered HTML even though JS toggle behaviour requires E2E testing
- Edit form must have hx-patch='/shootout/{id}/comments/{cid}' attribute, hx-target for the comment container, and hx-swap='outerHTML' for in-place replacement
- Alpine.js edit toggle: x-data='{editing: false}' on comment container, x-on:click='editing = true' on edit button, x-show='editing' on form, x-show='!editing' on display
- Verify the comments fragment GET endpoint works end-to-end: the hx-get URL on the shootout detail page must resolve to a handler that returns rendered HTML with comment content. This covers the J3 'Shootout detail page → Comments section loaded' transition.

**Truths Addressed:** 7, 8

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_shootout(chains=2), authenticated_client
**Assertions:**
- [dom_element] selector=[data-testid='comment-edit'], context=own comment visible
- [dom_absent] selector=[data-testid='comment-edit'], context=other user's comment
- [dom_element] selector=textarea[name='content'], context=edit form textarea exists in rendered comment HTML for own comment (Alpine.js controls visibility)
- [dom_element] selector=[data-testid='comment-edit-cancel'], context=cancel button exists in rendered comment HTML for own comment
- [dom_element] selector=[x-data], context=comment container has Alpine.js x-data for edit state toggle
- [dom_element] selector=[x-on\:click], [@click], context=edit button has Alpine.js click handler to toggle edit state
- [dom_element] selector=[hx-patch], context=edit form has hx-patch attribute targeting page handler for HTMX submission
- [dom_element] selector=[hx-target], context=edit form has hx-target attribute for in-place swap targeting
- [dom_element] method=GET, route=/shootout/{shootout.id}, auth=test_user, selector=[hx-get*='comments'], context=shootout detail page contains HTMX hx-get that loads comments fragment
- [http_status] method=GET, route=/shootout/{shootout.id}/comments, auth=test_user, expected_status=200, expected_content_type=text/html, context=Comments fragment endpoint returns 200 with HTML content (proves J3 hx-get load path works)
- [dom_element] method=GET, route=/shootout/{shootout.id}/comments, auth=test_user, selector=.comment-content, context=Comments fragment endpoint returns rendered HTML containing comment content (end-to-end load path verification)
- [http_status] method=PATCH, route=/shootout/{shootout.id}/comments/{comment.id}, auth=author_user, body=content=updated+text, expected_status=200, expected_content_type=text/html
- [dom_element] method=PATCH, route=/shootout/{shootout.id}/comments/{comment.id}, auth=author_user, selector=.comment-content, expected_text=updated text, context=HTML fragment response contains updated comment text for HTMX swap

---

### Validation Checkpoint: After Add inline comment editing UI

**Type:** http+dom
**Checks:**
- Shootout detail page contains HTMX hx-get that loads comments fragment (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_detail_page_has_htmx_comments_load`]
- Comments fragment endpoint returns 200 with rendered comment HTML content (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_comments_fragment_loads_with_content`]
- Comment edit button visible for author only (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_comment_edit_button_visible_for_author`]
- Comment edit button absent for non-author (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_comment_edit_button_absent_for_non_author`]
- Rendered comment HTML contains edit form with pre-filled textarea and cancel button (Alpine.js controlled) (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_comment_edit_form_markup_present`]
- Edit form has correct HTMX attributes (hx-patch, hx-target, hx-swap) for in-place submission (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_edit_form_htmx_attributes`]
- Edit button has Alpine.js click handler for toggling edit state (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_edit_button_alpine_toggle`]
- Page handler PATCH returns HTML fragment with updated comment text (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_comment_edit_patch_returns_html_fragment`]
- Edited comment shows (edited) indicator in HTML fragment (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/test_shootout_comments_html_fragment.py -k test_edited_comment_shows_indicator`]

---

### Story: Remove dead is_system_track references (`05-remove-is-system-track`)

**Purpose:** Remove the hardcoded is_system_track: False from the backend context mapper and all frontend references (badges, delete suppression, type definitions)

**Agent:**
- model: codex
- skills: [gts-frontend-dev]
- tools: []

**Scope:**
- Modify: `apps/webapp/src/webapp/api/pages/context.py`
- Modify: `frontend/astro/src/pages/fragments/library/track_item.html.ts`
- Modify: `frontend/astro/src/pages/pages/di-tracks/detail.html.ts`
- Modify: `frontend/astro/src/components/SignalChain/DITrackSelectModal.tsx`
- Modify: `frontend/astro/src/lib/api.ts`

### Acceptance Criteria

- pages/context.py di_track_to_context() no longer returns is_system_track key
- track_item.html.ts no longer contains is_system_track badge or delete button suppression
- di-tracks/detail.html.ts no longer contains is_system_track badge
- DITrackSelectModal.tsx no longer references is_system_track
- api.ts type definitions no longer include is_system_track
- DI track list page renders without errors (200)
- DI track detail page renders without errors (200)
- DI track list items contain links to detail pages that navigate correctly
- Astro dist/ files are rebuilt and committed
- grep -r is_system_track in src/ and frontend/astro/src/ returns zero matches

### Architectural Context

- is_system_track is hardcoded to False in context.py:108 — never comes from DB or domain model
- Frontend references are purely cosmetic: badges and delete suppression
- After removal, all DI track templates should render identically (the field was always False, so badges never showed and delete was never suppressed)
- The Astro dist/ directory must be rebuilt after template changes
- Track list items link to detail pages via a[href] — verify this navigation works post-cleanup

### Navigation Guide

- Backend: apps/webapp/src/webapp/api/pages/context.py:108 — remove the 'is_system_track': False line
- Template: frontend/astro/src/pages/fragments/library/track_item.html.ts:86 (badge) and :95 (delete suppression)
- Template: frontend/astro/src/pages/pages/di-tracks/detail.html.ts:66 (badge)
- React: frontend/astro/src/components/SignalChain/DITrackSelectModal.tsx:229 (badge render)
- Types: frontend/astro/src/lib/api.ts:489,505 (DITrackDetail.is_system_track and DITrackListItem.is_system_track)
- Dist files auto-rebuild via just build-astro

### Dependencies from Prior Stories

- Story 01 added group_to_detail_context to context.py — same file modified here for di_track_to_context cleanup
- Story 04 added updated_at to comment_to_context in context.py — same file, different function

**Wiki Sections:** Frontend-Architecture

**Implementation Notes:**
- This is pure deletion — no new code needed
- In track_item.html.ts, remove the {% if track.is_system_track %} badge block AND the {% if not track.is_system_track %} delete suppression condition (keep the delete button, just remove the conditional wrapper)
- In detail.html.ts, remove the {% if track.is_system_track %} badge block
- In DITrackSelectModal.tsx, remove the {track.is_system_track && (...)} JSX expression
- In api.ts, remove is_system_track from both type definitions
- Run just build-astro after changes, then commit both src/ and dist/

**Truths Addressed:** 9, 10

### Test Spec

**Type:** integration
**Fixtures:** make_user, make_di_track, authenticated_client
**Assertions:**
- [http_status] method=GET, route=/library/di-tracks, auth=test_user, expected_status=200
- [dom_element] method=GET, route=/library/di-tracks, auth=test_user, selector=a[href*='/library/di-tracks/'], context=Track list items contain links to detail pages
- [http_status] method=GET, route=/library/di-tracks/{di_track.id}, auth=test_user, expected_status=200, context=Detail page renders without errors after is_system_track removal
- [dom_absent] selector=.is-system-track-badge, context=badge should not exist on list page
- [dom_absent] method=GET, route=/library/di-tracks/{di_track.id}, selector=.is-system-track-badge, context=badge should not exist on detail page

---

### Validation Checkpoint: After Remove dead is_system_track references

**Type:** quality
**Checks:**
- No is_system_track references remain in source files (excluding test files and dist/) (evidence: command, exit_code, output_tail) [cmd: `bash -c '! grep -r is_system_track apps/webapp/src/ frontend/astro/src/'`]
- DI track list page renders without errors and contains links to detail pages (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/ -k di_track_list`]
- DI track detail page renders without errors after is_system_track removal (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/ -k di_track_detail`]
- Track list to detail navigation works (link href resolves to 200) (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/integration/webapp/ -k test_track_list_to_detail_navigation`]
- Lint, type checks, and existing tests pass (evidence: command, exit_code, output_tail) [cmd: `just check`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. GET /library/chains/group?id=<uuid> returns the group detail page showing group name, description, and list of chains in the group | `apps/webapp/src/webapp/api/pages/chains.py`, `apps/webapp/src/webapp/api/pages/context.py` | Wire group detail page endpoint |
| 2. Clicking a group item link on the group list page navigates to the group detail page (no 404) | `apps/webapp/src/webapp/api/pages/chains.py`, `apps/webapp/src/webapp/api/pages/context.py` | Wire group detail page endpoint |
| 3. Creating a shootout with a signal chain not owned by the current user returns 404 | `apps/webapp/src/webapp/api/pages/shootouts.py` | Validate chain ownership on shootout creation |
| 4. Creating a shootout with a chain owned by the current user succeeds as before | `apps/webapp/src/webapp/api/pages/shootouts.py` | Validate chain ownership on shootout creation |
| 5. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with {"content": "updated text"} updates the comment body and returns the updated comment. EPIC CONTRACT OVERRIDE: the epic originally specified PATCH /api/v1/comments/<id> with {"body": str}, but locked user decisions decision-api-1 (nested routes under shootout resource) and decision-api-3 (field named 'content' matching DB column and existing CommentCreateRequest) mandate this shape instead. This is the authoritative contract. | `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py`, `apps/webapp/src/webapp/services/shootout_comment_service.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+1 more) | Add comment edit API endpoint |
| 6. PATCH /api/shootouts/{shootout_id}/comments/{comment_id} by a non-author returns 404 | `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_comment_repository.py`, `apps/webapp/src/webapp/services/shootout_comment_service.py`, `apps/webapp/src/webapp/api/v1/shootouts.py` (+1 more) | Add comment edit API endpoint |
| 7. Comment on shootout detail page shows an edit button for the author only | `frontend/astro/src/pages/fragments/shootouts/comment_edit_form.html.ts`, `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`, `apps/webapp/src/webapp/api/pages/shootouts.py` (+1 more) | Add inline comment editing UI |
| 8. Clicking edit shows an inline form; submitting updates the comment text in place via HTMX | `frontend/astro/src/pages/fragments/shootouts/comment_edit_form.html.ts`, `frontend/astro/src/pages/fragments/shootouts/comments.html.ts`, `apps/webapp/src/webapp/api/pages/shootouts.py` (+1 more) | Add inline comment editing UI |
| 9. Hardcoded is_system_track: False removed from pages/context.py | `apps/webapp/src/webapp/api/pages/context.py`, `frontend/astro/src/pages/fragments/library/track_item.html.ts`, `frontend/astro/src/pages/pages/di-tracks/detail.html.ts` (+2 more) | Remove dead is_system_track references |
| 10. Frontend is_system_track badge and delete-button suppression references removed | `apps/webapp/src/webapp/api/pages/context.py`, `frontend/astro/src/pages/fragments/library/track_item.html.ts`, `frontend/astro/src/pages/pages/di-tracks/detail.html.ts` (+2 more) | Remove dead is_system_track references |
