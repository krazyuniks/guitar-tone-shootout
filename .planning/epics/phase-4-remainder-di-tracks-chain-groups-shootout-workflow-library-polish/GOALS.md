# Goal-Backward Analysis: Phase 4 Remainder — DI Tracks, Chain Groups, Shootout Workflow, Library Polish

## Goal

Users can upload DI tracks, organise signal chains into groups with permutation-based generation, create shootouts through a multi-step wizard, and manage their gear library at the model level — completing the full application layer before Phase 5 processing.

## Observable Truths

1. User can upload a DI track file and it appears in their library with metadata
2. User can browse and play back DI tracks with an audio player
3. User can create a signal chain group, configure gear options per slot, and generate permutation chains
4. User can create a shootout via wizard: select chains (individual or from group) → select DI track → review → submit
5. User can view a shootout detail page showing chains, DI track, and pre-processing status
6. User can add/remove individual gear models to their library via checkboxes on the gear detail page
7. Gear detail page shows all models with availability and library status

## Required Artifacts

### Truth 1: User can upload a DI track
| Artifact | Location | Status |
|----------|----------|--------|
| DITrack domain entity | `libs/core/src/core/domain/entities/di_track.py` | EXISTS |
| DITrack ORM model | `apps/webapp/src/webapp/adapters/persistence/models/shootout.py` | EXISTS |
| DITrackRepository | `apps/webapp/src/webapp/adapters/persistence/repositories/di_track_repository.py` | EXISTS |
| DITrackService.upload() | `apps/webapp/src/webapp/services/di_track_service.py` | EXISTS |
| POST /api/v1/di-tracks | `apps/webapp/src/webapp/api/v1/di_tracks.py` | MISSING |
| GET /api/v1/di-tracks | `apps/webapp/src/webapp/api/v1/di_tracks.py` | MISSING |
| GET /api/v1/di-tracks/{id} | `apps/webapp/src/webapp/api/v1/di_tracks.py` | MISSING |
| DI track upload Pydantic schemas | `apps/webapp/src/webapp/api/v1/schemas/di_track.py` | MISSING |
| Upload UI template | `frontend/astro/src/pages/library/di-tracks.html.ts` | NEEDS UPDATE |

### Truth 2: User can browse and play back DI tracks
| Artifact | Location | Status |
|----------|----------|--------|
| GET /api/v1/di-tracks/{id}/stream | `apps/webapp/src/webapp/api/v1/di_tracks.py` | MISSING |
| HTMX DI tracks browse | `apps/webapp/src/webapp/api/v1/html.py` | EXISTS |
| HTMX library tracks | `apps/webapp/src/webapp/api/v1/html.py` | EXISTS |
| Audio player in browse template | `frontend/astro/src/pages/di-tracks.html.ts` | NEEDS UPDATE |
| Audio player in library template | `frontend/astro/src/pages/library/di-tracks.html.ts` | NEEDS UPDATE |
| DI track seed import script | `scripts/seed_di_tracks.py` | MISSING |

### Truth 3: User can create chain groups and generate permutations
| Artifact | Location | Status |
|----------|----------|--------|
| SignalChainGroup domain entity | `libs/core/src/core/domain/entities/signal_chain_group.py` | EXISTS |
| SignalChainGroup ORM model | `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py` | EXISTS |
| SignalChainGroupRepository | `apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain_group_repository.py` | EXISTS |
| SignalChainGroupService | `apps/webapp/src/webapp/services/signal_chain_group_service.py` | MISSING |
| Group CRUD API endpoints | `apps/webapp/src/webapp/api/v1/signal_chain_groups.py` | MISSING |
| Group Pydantic schemas | `apps/webapp/src/webapp/api/v1/schemas/signal_chain_group.py` | MISSING |
| Permutation generation endpoint | `apps/webapp/src/webapp/api/v1/signal_chain_groups.py` | MISSING |
| Group HTMX fragments | `apps/webapp/src/webapp/api/v1/html.py` | MISSING |
| Group management templates | `frontend/astro/src/pages/library/groups.html.ts` | NEEDS UPDATE |

### Truth 4: User can create a shootout via wizard
| Artifact | Location | Status |
|----------|----------|--------|
| Wizard page template | `frontend/astro/src/pages/shootout_create.html.ts` | EXISTS |
| Wizard step fragments | `frontend/astro/src/pages/fragments/shootouts/create/` | EXISTS |
| HTMX chain list endpoint | `apps/webapp/src/webapp/api/v1/html.py` (line 617) | EXISTS |
| HTMX DI track list endpoint | `apps/webapp/src/webapp/api/v1/html.py` (line 649) | EXISTS |
| HTMX submit endpoint | `apps/webapp/src/webapp/api/v1/html.py` (line 680) | EXISTS |
| Group-based chain selection | `apps/webapp/src/webapp/api/v1/html.py` | MISSING |

### Truth 5: User can view shootout detail with pre-processing state
| Artifact | Location | Status |
|----------|----------|--------|
| Shootout detail page route | `apps/webapp/src/webapp/api/pages.py` (line 557) | EXISTS |
| Shootout detail template | `frontend/astro/src/pages/shootout_detail.html.ts` | EXISTS |
| Pre-processing state display | template update needed | NEEDS UPDATE |

### Truth 6: User can manage gear library at model level
| Artifact | Location | Status |
|----------|----------|--------|
| UserGear domain entity | `libs/core/src/core/domain/entities/gear.py` (line 163) | NEEDS MIGRATION |
| UserGear ORM model | `apps/webapp/src/webapp/adapters/persistence/models/user_gear.py` | NEEDS MIGRATION |
| Alembic migration | `infrastructure/migrations/versions/` | MISSING |
| Library API endpoints | `apps/webapp/src/webapp/api/v1/library.py` | NEEDS UPDATE |
| Library Pydantic schemas | `apps/webapp/src/webapp/api/v1/schemas/library.py` | NEEDS UPDATE |
| HTMX library fragments | `apps/webapp/src/webapp/api/v1/html.py` | NEEDS UPDATE |
| Model-level checkbox UI | `frontend/astro/src/pages/gear/detail.html.ts` | NEEDS UPDATE |

### Truth 7: Gear detail shows models with library status
| Artifact | Location | Status |
|----------|----------|--------|
| Gear detail page route | `apps/webapp/src/webapp/api/pages.py` (line 205) | EXISTS |
| Gear detail template | `frontend/astro/src/pages/gear/detail.html.ts` | EXISTS |
| Model listing with status | template update needed | NEEDS UPDATE |

## Required Wiring

### POST /api/v1/di-tracks (upload)
- FastAPI route with `UploadFile` parameter
- Multipart form data: file + name + description + guitar + pickup
- Save file to `/app/uploads/di-tracks/{user_id}/{uuid}.{ext}`
- Delegate to existing `DITrackService.upload()`
- Return `DITrackResponse` schema
- CurrentUser auth dependency

### GET /api/v1/di-tracks/{id}/stream
- FastAPI route returning `FileResponse`
- Content-type based on file extension (.wav, .flac, etc.)
- Ownership check OR public access
- `Accept-Ranges` header for seeking

### Signal Chain Group CRUD
- FastAPI router at `/api/v1/signal-chain-groups/`
- SignalChainGroupService wraps repository
- POST `/{id}/generate` triggers permutation creation
- Permutations create real SignalChain entities via SignalChainService
- CurrentUser auth on all endpoints

### UserGear FK Migration
- Domain: `UserGear.gear_id` → `UserGear.gear_model_id`
- ORM: FK from `user_gear.gear_id` → `gear.id` changes to `user_gear.gear_model_id` → `gear_models.id`
- Alembic: rename column + update FK + update unique constraint
- Downstream: library.py, html.py, schemas/library.py, pages.py, templates

## Test Specifications

| Truth | Test Level | Test Name | Location |
|-------|------------|-----------|----------|
| Truth 1 | Integration | test_di_track_upload_creates_record | tests/integration/webapp/ |
| Truth 1 | Integration | test_di_track_upload_rejects_invalid_format | tests/integration/webapp/ |
| Truth 1 | Integration | test_di_track_list_returns_user_tracks | tests/integration/webapp/ |
| Truth 2 | Integration | test_di_track_stream_returns_audio | tests/integration/webapp/ |
| Truth 3 | Integration | test_signal_chain_group_crud | tests/integration/webapp/ |
| Truth 3 | Integration | test_group_permutation_generates_chains | tests/integration/webapp/ |
| Truth 4 | Integration | test_shootout_create_with_group_chains | tests/integration/webapp/ |
| Truth 5 | Integration | test_shootout_detail_shows_pre_processing | tests/integration/webapp/ |
| Truth 6 | Integration | test_library_add_gear_model | tests/integration/webapp/ |
| Truth 6 | Integration | test_library_remove_gear_model | tests/integration/webapp/ |
| Truth 7 | Integration | test_gear_detail_shows_models_with_status | tests/integration/webapp/ |
| All | Regression | test_regression (updated) | tests/e2e/python/ |
