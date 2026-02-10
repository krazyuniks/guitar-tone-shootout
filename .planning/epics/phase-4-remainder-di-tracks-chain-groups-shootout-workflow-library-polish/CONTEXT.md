# Epic Context: Phase 4 Remainder — DI Tracks, Chain Groups, Shootout Workflow, Library Polish

## Sources Loaded

| Source | Found | Relevance |
|--------|-------|-----------|
| IMPLEMENTATION.md | Yes | Phase 4A–4D scope, deliverables, archive mapping |
| GTS-Technical-Architecture.md | Yes | Domain model, auth, patterns |
| AGENTS.md | Yes | Development workflow, rules |
| authentication.md | Yes | JWT auth, CurrentUser dependency |
| testing-policy.md | Yes | TDD, real services, mock policy |
| frontend-standards.md | Yes | Astro SSG, Jinja2 SSR, HTMX, data-testid |

## Detected Stack

- Backend: FastAPI, SQLAlchemy 2.0, PostgreSQL (gts_core), Redis
- Frontend: Astro SSG (pre-bundled), Jinja2 SSR, HTMX, Alpine.js
- Testing: pytest, Playwright
- Infrastructure: Docker, uv workspaces, just commands
- Audio: libs/audio (WaveformExtractor for DI tracks)

## Relevant Domain Entities

| Entity | Location | Relevance |
|--------|----------|-----------|
| DITrack | `libs/core/src/core/domain/entities/di_track.py` | 4A: Upload, browse, playback |
| SignalChainGroup | `libs/core/src/core/domain/entities/signal_chain_group.py` | 4B: Group CRUD, permutations |
| Shootout | `libs/core/src/core/domain/entities/shootout.py` | 4C: Wizard creation flow |
| ShootoutChain | `libs/core/src/core/domain/entities/shootout.py` | 4C: Chain links in shootout |
| SignalChain | `libs/core/src/core/domain/entities/signal_chain.py` | 4B/4C: Chain selection |
| Gear | `libs/core/src/core/domain/entities/gear.py` | 4D: Browse/detail polish |
| GearModel | `libs/core/src/core/domain/entities/gear.py` | 4D: Model-level checkboxes |
| UserGear | `libs/core/src/core/domain/entities/gear.py` | 4D: Library management |
| WaveformData | `libs/core/src/core/domain/value_objects/waveform_data.py` | 4A: Waveform display |
| AudioChecksum | `libs/core/src/core/domain/value_objects/audio_checksum.py` | 4A: File integrity |

## Existing Implementation (What Already Exists)

### ORM Models (all exist)
- DITrack, Shootout, ShootoutChain, AudioSegment — `models/shootout.py`
- SignalChain, SignalChainBlock, SignalChainGroup — `models/signal_chain.py`
- Gear, GearMake, GearTag — `models/gear.py`
- GearModel — `models/gear_model.py`
- UserGear — `models/user_gear.py`

### Repositories (all exist)
- di_track_repository, shootout_repository, signal_chain_repository
- signal_chain_group_repository, gear_repository, user_gear_repository

### Services (exist but incomplete)
- `di_track_service.py` — upload() with validation, checksum, dedup. Working.
- `shootout_service.py` — CRUD. Working.
- `signal_chain_service.py` — CRUD. Working.
- `gear_service.py` — search/list. Working.
- **Missing: SignalChainGroupService** — no service layer for groups

### API Endpoints (partial)
- `GET/POST/DELETE /api/v1/shootouts/` — Full CRUD exists
- `GET/POST/PUT/DELETE /api/v1/signal-chains/` — Full CRUD exists
- `DELETE /api/v1/di-tracks/{id}` — Only delete exists (NO upload, list, get, stream)
- `GET /api/v1/gear/`, `GET /api/v1/gear/{id}` — Browse/detail exists
- `GET/POST/DELETE /api/v1/library/gear` — Library CRUD exists (gear-level, needs migration to model-level)
- **No signal chain group API endpoints exist**

### HTMX Endpoints (mostly exist in html.py)
- `GET /api/v1/html/gear/list` — Gear browse fragment
- `GET /api/v1/html/library/my-gear/list` — Library gear fragment
- `GET /api/v1/html/my-gear/results` — Library gear results (paginated)
- `GET /api/v1/html/di-tracks/results` — Public DI tracks browse
- `GET /api/v1/html/library/tracks` — Library DI tracks
- `GET /api/v1/html/library/chains` — Library chains
- `GET /api/v1/html/library/shootouts` — Library shootouts
- `GET /api/v1/html/shootout-create/chains` — Wizard step 1 chain list
- `GET /api/v1/html/shootout-create/ditracks` — Wizard step 2 DI track list
- `POST /api/v1/html/shootout-create` — Wizard submit (creates shootout)
- `GET /api/v1/html/shootouts/sections` — Public shootouts sections
- **Missing: group-related HTMX endpoints**

### Frontend Templates (templates exist, some are shells)
- Shootout wizard fragments: step1-chains, step2-ditrack, step3-review — **working**
- DI track pages: browse, detail, library — templates exist, need audio player
- Gear pages: browse, detail — templates exist
- Library pages: chains, my_gear, di-tracks, shootouts, groups — templates exist

## What's Missing (Epic Scope)

### 4A: DI Track Management
- Upload endpoint (POST /api/v1/di-tracks with multipart/form-data)
- List endpoint (GET /api/v1/di-tracks)
- Get endpoint (GET /api/v1/di-tracks/{id})
- Stream/playback endpoint (GET /api/v1/di-tracks/{id}/stream)
- Upload UI with drag-and-drop in templates
- HTML5 audio player in browse/library templates
- Seed import management command

### 4B: Signal Chain Groups
- SignalChainGroupService (no service layer exists)
- Group CRUD API endpoints (create, list, get, update, delete)
- Permutation batch generation (create real SignalChain entities)
- Group management UI (templates + HTMX fragments)

### 4C: Shootout Wizard
- Chain selection from groups (currently only individual chains)
- Shootout detail page polish for pre-processing state

### 4D: Gear Library Polish
- UserGear FK migration (gear_id → gear_model_id)
- Model-level library management API (add/remove at GearModel level)
- Model-level checkboxes on gear detail page
- Library status indicator on gear detail

### Infrastructure Prerequisites (completed by user)
- Storage bind mount (replace Docker named volumes) — DONE
- UserGear FK correction (gear_id → gear_model_id) — IN THIS EPIC

## Relevant Patterns

- Services own transactions (`async with session.begin():`)
- Repository uses `joinedload` only (no selectinload)
- All relationships use `lazy="raise"`
- JWT auth via CurrentUser dependency
- Return 404 (not 403) for ownership violations
- All interactive elements need `data-testid`
- SSR page links in Astro need `data-astro-reload`
- Frontend: Astro .html.ts → build → dist/ committed

## Locked Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UserGear FK | Include migration in this epic | ORM still has gear_id → gear.id; needs gear_model_id |
| DI seed import | Management command (Python script via `just`) | Bulk-import existing DI track files from disk |
| Permutation output | Create real SignalChain entities | Users select generated chains normally in wizard |
| Testing strategy | Integration + Regression | Integration tests per task; regression test update at end |
| DI track streaming | FastAPI FileResponse with content-type | Auth check for ownership; public tracks streamable by anyone |
| File storage path | `/app/uploads/di-tracks/{user_id}/{uuid}.{ext}` | Existing `upload_data` volume mount |
| Wizard HTMX | Existing endpoints are functional | Step 1-3 HTMX endpoints already exist in html.py |
