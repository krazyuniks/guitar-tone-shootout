# Task Breakdown: E86 — Phase 4 Remainder

## Dependency Graph

```
A1 (unblocked)
A1 → A2
A2 → D1
D1 → D2

B1 (unblocked)
B1 → B2
B2 → B3
B4 (unblocked)

C1 (unblocked)
C1 → C2
C1, C2 → C3

C2 → E1
B2 → E2

B3, B4, C3, D2, E1, E2 → F1
```

---

### A1: UserGear FK Migration — Domain + ORM + Alembic

**Objective:** Migrate UserGear from gear-level to model-level linking. Change the foreign key from `gear_id → gear.id` to `gear_model_id → gear_models.id` across domain entity, ORM model, and database schema. This is a breaking change — all downstream consumers are fixed in A2.

**Citation:** Epic #86 Infrastructure Prerequisites: "UserGear FK correction (gear_id → gear_model_id)"

**Acceptance Criteria:**
- [ ] `UserGear` domain entity in `libs/core/src/core/domain/entities/gear.py` has `gear_model_id: UUID` instead of `gear_id: UUID`
- [ ] `UserGear` ORM model in `models/user_gear.py` has `gear_model_id` FK pointing to `gear_models.id`
- [ ] Unique constraint updated from `(user_id, gear_id)` to `(user_id, gear_model_id)`
- [ ] Alembic migration renames column, updates FK, updates unique constraint and indexes
- [ ] Migration is reversible (downgrade works)
- [ ] `just check` passes (lint + types — downstream breakage expected, fixed in A2)

**Scope:**
- Modify: `libs/core/src/core/domain/entities/gear.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/user_gear.py`
- Create: `infrastructure/migrations/versions/0003_user_gear_fk_to_gear_model.py`

**Dependencies:** None

**Labels:** `project:webapp`, `breaking-change`

---

### A2: Fix UserGear FK Downstream Consumers

**Objective:** Fix all code that references `UserGear.gear_id` to use `UserGear.gear_model_id` instead. This includes repositories, API endpoints, HTMX fragments, schemas, and page routes. After this task, the codebase compiles and all existing tests pass with the new FK.

**Citation:** Goal-backward: breaking change blast radius analysis for UserGear FK

**Acceptance Criteria:**
- [ ] `user_gear_repository.py` queries use `gear_model_id`
- [ ] `library.py` API endpoints use `gear_model_id` (add/list/remove)
- [ ] `schemas/library.py` request/response schemas use `gear_model_id`
- [ ] `html.py` HTMX fragments join on `gear_model_id` (my_gear_results_fragment, library_my_gear_list_fragment)
- [ ] `pages.py` gear routes handle `gear_model_id` correctly
- [ ] Integration test verifies library add/list/remove with `gear_model_id`
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/adapters/persistence/repositories/user_gear_repository.py`
- Modify: `apps/webapp/src/webapp/api/v1/library.py`
- Modify: `apps/webapp/src/webapp/api/v1/schemas/library.py`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Modify: `apps/webapp/src/webapp/api/pages.py`
- Create: `tests/integration/webapp/test_user_gear_model_fk.py`

**Dependencies:** A1

**Labels:** `project:webapp`, `breaking-change-fix`

---

### B1: DI Track Upload Endpoint

**Objective:** Add the upload endpoint for DI tracks. Accept multipart file upload with metadata, save file to storage, create database record via existing `DITrackService.upload()`, and return the created track. Also add list and get endpoints for completeness.

**Citation:** Epic #86 4A: "DI track upload endpoint with validation (format, duration, size)"

**Acceptance Criteria:**
- [ ] `POST /api/v1/di-tracks` accepts `UploadFile` + form fields (name, description, guitar, pickup)
- [ ] File saved to `/app/uploads/di-tracks/{user_id}/{uuid}.{ext}` with correct permissions
- [ ] `DITrackService.upload()` called with correct parameters
- [ ] Returns 201 with `DITrackResponse` on success
- [ ] Returns 400 for invalid format, empty name, duplicate checksum
- [ ] `GET /api/v1/di-tracks` lists current user's tracks (paginated)
- [ ] `GET /api/v1/di-tracks/{id}` returns single track (ownership check)
- [ ] All endpoints require `CurrentUser` authentication
- [ ] Pydantic schemas for `DITrackResponse` created
- [ ] Integration test for upload, list, get, and validation rejection
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/api/v1/di_tracks.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/di_track.py`
- Create: `tests/integration/webapp/test_di_track_upload.py`

**Dependencies:** None

**Labels:** `project:webapp`

---

### B2: DI Track Stream Endpoint

**Objective:** Add a streaming endpoint that serves DI track audio files with correct content-type headers. Support range requests for seeking in the audio player. Allow public access to shared tracks while enforcing ownership for private tracks.

**Citation:** Epic #86 4A: "Stream/playback endpoint"

**Acceptance Criteria:**
- [ ] `GET /api/v1/di-tracks/{id}/stream` returns `FileResponse` with correct `Content-Type`
- [ ] Content-type mapped correctly: `.wav` → `audio/wav`, `.flac` → `audio/flac`, `.ogg` → `audio/ogg`, `.mp3` → `audio/mpeg`
- [ ] Track owner can always stream their tracks
- [ ] Returns 404 for non-existent tracks or unauthorized access
- [ ] Integration test verifies stream response headers and content
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/api/v1/di_tracks.py`
- Create: `tests/integration/webapp/test_di_track_stream.py`

**Dependencies:** B1

**Labels:** `project:webapp`

---

### B3: DI Track Audio Player UI

**Objective:** Add HTML5 audio player to DI track browse and library templates. Add upload form to the library DI tracks page. Wire audio player to the stream endpoint. All interactive elements have `data-testid` attributes.

**Citation:** Epic #86 4A: "Browse page with audio player"

**Acceptance Criteria:**
- [ ] Public browse page (`di-tracks.html.ts`) shows inline audio player per track
- [ ] Library page (`library/di-tracks.html.ts`) shows inline audio player per track
- [ ] Audio player `src` points to `/api/v1/di-tracks/{id}/stream`
- [ ] Library page has upload form (file input + metadata fields) posting to upload endpoint
- [ ] Upload form uses HTMX to submit without full page reload
- [ ] All interactive elements have `data-testid` attributes
- [ ] `just build-astro` succeeds
- [ ] `just check` passes

**Scope:**
- Modify: `frontend/astro/src/pages/di-tracks.html.ts`
- Modify: `frontend/astro/src/pages/library/di-tracks.html.ts`
- Modify: `frontend/astro/src/pages/fragments/library/track_item.html.ts`
- Modify: `frontend/astro/src/pages/fragments/di-tracks/public_browse.html.ts`

**Dependencies:** B2

**Labels:** `project:frontend`

---

### B4: DI Track Seed Import Command

**Objective:** Create a management command to bulk-import DI track audio files from a directory on disk into the database. The command reads audio files, extracts metadata, and creates records via `DITrackService`. Callable via a `just` recipe.

**Citation:** Epic #86 4A: "Seed import from existing files"

**Acceptance Criteria:**
- [ ] Script at `scripts/seed_di_tracks.py` accepts directory path and user ID arguments
- [ ] Recursively finds `.wav`, `.flac`, `.ogg`, `.mp3` files in directory
- [ ] Creates DITrack record for each file via `DITrackService.upload()`
- [ ] Skips duplicates (checksum match) without error
- [ ] Copies files to storage path (`/app/uploads/di-tracks/`)
- [ ] Reports summary: imported count, skipped count, error count
- [ ] `just seed-di-tracks` recipe added to Justfile
- [ ] `just check` passes

**Scope:**
- Create: `scripts/seed_di_tracks.py`
- Modify: `Justfile`

**Dependencies:** None

**Labels:** `project:scripts`

---

### C1: SignalChainGroupService + CRUD API

**Objective:** Create the service layer for signal chain groups and REST API endpoints for CRUD operations. The service wraps the existing repository. API follows the same patterns as shootouts API (CurrentUser auth, ownership checks, 404 for unauthorized).

**Citation:** Epic #86 4B: "Signal chain group CRUD API"

**Acceptance Criteria:**
- [ ] `SignalChainGroupService` with create, get_by_id, get_by_user_id, update, delete methods
- [ ] `GET /api/v1/signal-chain-groups` lists current user's groups
- [ ] `POST /api/v1/signal-chain-groups` creates a group (name, description, base_chain_id, slot_positions, gear_options)
- [ ] `GET /api/v1/signal-chain-groups/{id}` returns group detail (ownership check)
- [ ] `PUT /api/v1/signal-chain-groups/{id}` updates group (ownership check)
- [ ] `DELETE /api/v1/signal-chain-groups/{id}` deletes group (ownership check)
- [ ] Pydantic schemas for request/response
- [ ] All endpoints require `CurrentUser` authentication
- [ ] Integration test for full CRUD cycle
- [ ] `just check` passes

**Scope:**
- Create: `apps/webapp/src/webapp/services/signal_chain_group_service.py`
- Create: `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/signal_chain_group.py`
- Create: `tests/integration/webapp/test_signal_chain_group_crud.py`

**Dependencies:** None

**Labels:** `project:webapp`

---

### C2: Permutation Batch Generation

**Objective:** Add permutation generation to the group service. When triggered, compute all gear combinations from the group's slot positions and gear options, then create real `SignalChain` entities in the user's library. Respects the domain entity's `max_permutations` limit (default 27).

**Citation:** Epic #86 4B: "Permutation-based batch generation (N amps × M IRs)"

**Acceptance Criteria:**
- [ ] `SignalChainGroupService.generate_permutations(group_id)` method
- [ ] Computes cartesian product of gear options across slots
- [ ] Creates real `SignalChain` entities via `SignalChainService` for each permutation
- [ ] Each generated chain named with group name + option description
- [ ] Respects `max_permutations` limit — returns error if exceeded
- [ ] Uses `include_null` flag to include "no gear" as an option per slot
- [ ] `POST /api/v1/signal-chain-groups/{id}/generate` endpoint triggers generation
- [ ] Returns list of created chain IDs
- [ ] Integration test: 2 amps × 2 IRs = 4 chains created
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/services/signal_chain_group_service.py`
- Modify: `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`
- Create: `tests/integration/webapp/test_signal_chain_group_permutations.py`

**Dependencies:** C1

**Labels:** `project:webapp`

---

### C3: Signal Chain Group Management UI

**Objective:** Add group management templates and HTMX fragments. Users can create, view, edit, and delete groups from the library page. The group detail page shows current configuration and a "Generate Chains" button.

**Citation:** Epic #86 4B: "Group management UI"

**Acceptance Criteria:**
- [ ] Library groups page shows user's groups with name, base chain, estimated permutation count
- [ ] HTMX fragment endpoint `GET /api/v1/html/library/groups` returns group list
- [ ] Group create/edit form with fields: name, description, base chain selector, slot configuration
- [ ] Group detail shows slot positions with gear options per slot
- [ ] "Generate Chains" button triggers permutation generation via HTMX POST
- [ ] Delete button with confirmation
- [ ] All interactive elements have `data-testid` attributes
- [ ] `just build-astro` succeeds
- [ ] `just check` passes

**Scope:**
- Modify: `frontend/astro/src/pages/library/groups.html.ts`
- Create: `frontend/astro/src/pages/fragments/library/group_detail.html.ts`
- Modify: `frontend/astro/src/pages/fragments/library/group_item.html.ts`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`

**Dependencies:** C1, C2

**Labels:** `project:frontend`

---

### D1: Model-Level Gear Library Management API

**Objective:** Update the library API to work with `gear_model_id` instead of `gear_id`. Users add/remove individual gear models to their library. The list endpoint returns model-level data including gear name, platform, and size.

**Citation:** Epic #86 4D: "Model-level checkboxes for gear library management"

**Acceptance Criteria:**
- [ ] `POST /api/v1/library/gear` accepts `gear_model_id` (not `gear_id`)
- [ ] `GET /api/v1/library/gear` returns model-level items with gear name, platform, size
- [ ] `DELETE /api/v1/library/gear/{user_gear_id}` still works (no change needed)
- [ ] `POST /api/v1/library/gear/{gear_model_id}/toggle` adds if not in library, removes if already in library
- [ ] Returns current state (added/removed) for UI update
- [ ] Unique constraint enforced: same user can't add same model twice
- [ ] Integration test for add, list, remove, toggle, and duplicate rejection
- [ ] `just check` passes

**Scope:**
- Modify: `apps/webapp/src/webapp/api/v1/library.py`
- Modify: `apps/webapp/src/webapp/api/v1/schemas/library.py`
- Create: `tests/integration/webapp/test_library_model_level.py`

**Dependencies:** A2

**Labels:** `project:webapp`

---

### D2: Gear Detail Page with Model Listing + Library Checkboxes

**Objective:** Update the gear detail page template to show all models with platform, size, and download status. For authenticated users, show a checkbox per model indicating library membership. Checkboxes toggle via HTMX using the toggle endpoint from D1.

**Citation:** Epic #86 4D: "Gear detail page with model listing" + "Model-level checkboxes"

**Acceptance Criteria:**
- [ ] Gear detail page lists all models grouped by platform
- [ ] Each model shows: platform icon, size label, download status, file size
- [ ] Authenticated users see a checkbox per model
- [ ] Checkbox state reflects current library membership
- [ ] Clicking checkbox calls `POST /api/v1/library/gear/{gear_model_id}/toggle` via HTMX
- [ ] Checkbox updates optimistically (Alpine.js toggle + server confirmation)
- [ ] Unauthenticated users see models without checkboxes
- [ ] All interactive elements have `data-testid` attributes
- [ ] HTMX fragment for model list with library status
- [ ] `just build-astro` succeeds
- [ ] `just check` passes

**Scope:**
- Modify: `frontend/astro/src/pages/gear/detail.html.ts`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Modify: `apps/webapp/src/webapp/api/pages.py`

**Dependencies:** D1

**Labels:** `project:frontend`

---

### E1: Wizard Chain Selection from Groups

**Objective:** Extend the shootout creation wizard step 1 to allow selecting chains from a group. When a user picks a group, its generated chains are loaded and available for selection alongside individually created chains.

**Citation:** Epic #86 4C: "Chain selection from groups or individual chains"

**Acceptance Criteria:**
- [ ] Wizard step 1 shows two sections: "My Chains" and "From Groups"
- [ ] "From Groups" section lists user's groups with chain count
- [ ] Clicking a group expands to show its generated chains
- [ ] User can select individual chains from the expanded group
- [ ] Selected chains (from any source) appear in the selection summary
- [ ] HTMX endpoint `GET /api/v1/html/shootout-create/group-chains/{group_id}` returns chain list for group
- [ ] Minimum 2 chains required (validation preserved)
- [ ] Integration test for wizard with group-based chain selection
- [ ] `just check` passes

**Scope:**
- Modify: `frontend/astro/src/pages/fragments/shootouts/create/step1-chains.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/create/chain-list.html.ts`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Create: `tests/integration/webapp/test_shootout_wizard_groups.py`

**Dependencies:** C2

**Labels:** `project:webapp`, `project:frontend`

---

### E2: Shootout Detail Page Pre-Processing State

**Objective:** Polish the shootout detail page to properly display the pre-processing state. Show the selected chains with their gear info, the DI track reference with playback, and clear status indicators.

**Citation:** Epic #86 4C: "Shootout detail page (pre-processing state)"

**Acceptance Criteria:**
- [ ] Detail page shows shootout name, description, creation date
- [ ] Chain list shows each chain with position, name, and gear summary
- [ ] DI track section shows track name, duration, and audio player (stream link)
- [ ] Status badge shows current state (pending, processing, complete, failed)
- [ ] "Pending" state has explanatory text about awaiting processing
- [ ] Page works for shootouts with 2-20 chains
- [ ] All interactive elements have `data-testid` attributes
- [ ] `just build-astro` succeeds
- [ ] `just check` passes

**Scope:**
- Modify: `frontend/astro/src/pages/shootout_detail.html.ts`
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`
- Modify: `apps/webapp/src/webapp/api/pages.py`

**Dependencies:** B2

**Labels:** `project:frontend`

---

### F1: Regression Test Updates for All New Endpoints

**Objective:** Update the regression test suite to verify all new endpoints and pages added by this epic return expected responses. This is the final verification that the full stack is wired correctly.

**Citation:** Testing strategy: "Integration + Regression" — regression test update at end

**Acceptance Criteria:**
- [ ] DI tracks upload page returns 200 with upload form
- [ ] DI tracks browse page returns 200 with track listing
- [ ] DI tracks library page returns 200 for authenticated user
- [ ] Signal chain groups library page returns 200 for authenticated user
- [ ] Shootout wizard page returns 200 with step 1 content
- [ ] Shootout detail page returns 200 with chain listing
- [ ] Gear detail page returns 200 with model listing
- [ ] All new HTMX fragment endpoints return 200
- [ ] `just test-regression` passes
- [ ] `just check` passes

**Scope:**
- Modify: `tests/e2e/python/tests/test_regression.py`

**Dependencies:** B3, B4, C3, D2, E1, E2

**Labels:** `project:testing`
