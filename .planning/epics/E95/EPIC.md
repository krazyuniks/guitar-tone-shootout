---
github_issue: 95
title: "Phase 4 Completion — DI Tracks, Groups, Shootout Workflow, Content APIs, Platform Infra"
state: OPEN
labels: ["epic"]
fetched: 2026-02-13T17:08:31Z
---

## Epic: Phase 4 Completion

Complete all remaining Phase 4 web application features identified in the gap analysis. Phases 4A–4E are partially implemented or pending. This epic fills every gap to provide a solid foundation for Phase 5.

### Context

Phase 4 (core) delivered FastAPI auth, CRUD services, API endpoints, SSR pages, and the React SignalChainBuilder. But gap analysis against the archive revealed significant missing functionality in the sub-phases:

- **4A:** Frontend/API contract mismatch, IR upload service, asset/file serving — all missing
- **4B:** Router not mounted in main.py — endpoints exist but unreachable
- **4C:** Shootout wizard needs end-to-end validation, comments feature missing
- **4D:** Tags, Presets, Block Types APIs not implemented despite entities existing
- **4E:** Entirely pending — exceptions, error pages, audit, notifications, OAuth providers

### Pre-requisites

Phases 1–4 (core) ✅ complete.

**Can run in parallel with:** Phase 5 Pipeline epic (5A/5B/5D)

### Scope

#### Phase 4A — DI Track & IR Upload (Partial → Complete)

**Exists:** Upload endpoint, DITrackService, partial upload UI
**Gaps:**
- Fix frontend/API contract mismatch (URL: `/di-tracks/upload` → `/di-tracks`, fields: `title`→`name`, `pickups`→`pickup`)
- DI track browse page with real data, pagination, waveforms
- Upload UI with drag-and-drop, progress indicator, metadata form (guitar, pickup, notes)
- Library page showing user's DI tracks with delete capability
- System/seed DI tracks for testing and demo
- Waveform extraction on upload (WaveformExtractor from `libs/audio`)
- Audio metadata extraction (duration, sample rate, channels)
- `POST /api/v1/irs/upload` — community IR upload creating Gear + GearModel with `source="community"`
- Asset/file serving service — HMAC signed URLs, ownership validation, path traversal prevention
- File serving endpoint (`/api/v1/files/*`) for DI tracks, IRs, audio segments

**Archive refs:** `di_track_service.py`, `ir_upload_service.py`, `asset_service.py`, `files.py`

#### Phase 4B — Signal Chain Groups (Partial → Complete)

**Exists:** Group CRUD API and service code
**Gaps:**
- Mount `signal_chain_groups` router in `apps/webapp/src/webapp/main.py`
- Verify group CRUD API endpoints functional end-to-end
- Batch chain generation endpoint (N amps × M IRs)
- Group list page with tabs
- Group detail page with chain list
- Builder integration for group creation

**Archive refs:** `signal_chain_groups.py`, `signal_chain_group_service.py`

#### Phase 4C — Shootout Workflow (Partial → Complete)

**Depends on:** 4A (DI tracks must exist for selection)

**Exists:** Wizard page template, HTMX wizard fragments, submit endpoints
**Gaps:**
- Wizard step 1: chain selection from user's library (with group support from 4B)
- Wizard step 2: DI track selection modal with search/filter
- Wizard step 3: review and submit (summary of chains + DI track)
- Shootout detail page showing chains, DI track, processing status
- Validation: min 2 / max 20 chains, DI track required
- `ShootoutComment` entity + ORM model
- Comments CRUD API: `POST/GET/DELETE /api/v1/shootouts/{id}/comments`
- Comments HTMX fragment on shootout detail page

**Archive refs:** `fragments/shootouts/comments.html.ts`

#### Phase 4D — Library, Gear & Content APIs (Partial → Complete)

**Exists:** Model count wiring, save/remove toggle endpoints (partial)
**Gaps:**
- Gear model detail pages showing metadata, download status, audio preview
- Save/remove checkbox UI for bulk add/remove models to/from library
- Model counts on gear cards and detail pages
- Download status indicators on models
- Library sorting and filtering (date added, name, type; filter by gear type)
- Grid-aligned pagination (multiples of 3 for card layout)
- Tag CRUD API: `GET/POST/DELETE /api/v1/tags` with `TagService` + lowercase normalisation
- Preset CRUD API: `GET/POST/PUT/DELETE /api/v1/presets` with `PresetProcessor` for chain parameter validation
- Block types API: `GET /api/v1/block-types` listing built-in processor templates with effect parameter definitions
- License text display on gear detail pages

**Archive refs:** `tag_service.py`, `tags.py`, `preset_service.py`, `preset_processor.py`, `presets.py`, `block_type_registry.py`, `block_types.py`, `license_text.html.ts`

#### Phase 4E — Platform Infrastructure (Pending → Complete)

**Exists:** Nothing — entirely new
**Gaps:**
- Custom exception hierarchy: `AppException`, `NotFoundError`, `AuthorizationError`, `ConflictError`, `BadRequestError`, `ValidationError`
- Exception handlers for `AppException`, `HTTPException`, `RequestValidationError`, `SQLAlchemyError`, unhandled exceptions
- Content negotiation: HTML vs JSON error responses based on Accept header and route type
- Error sanitisation for production (strip stack traces)
- Custom 404 + 500 pages (Astro-built)
- nginx error pages (502, 503, 504 static HTML)
- Settings/account page at `/settings/account` (connected OAuth providers, account details)
- Dynamic `sitemap.xml` endpoint (static pages, public shootouts, gear pages)
- `AuditLog` ORM model + `AuditService` logging security-relevant events (login, CRUD operations)
- `UserNotification` ORM model + `NotificationService` (queue, get unread, mark read)
- Notification API endpoints (get unread, mark read, mark all read)
- Google OAuth provider
- GitHub OAuth provider
- Facebook OAuth provider
- Graceful shutdown with signal handlers (503 during drain)
- Test error endpoints (debug-mode only, used by Phase 6 E2E)

**Archive refs:** `exceptions.py`, `exception_handlers.py`, `content_negotiation.py`, `error_sanitizer.py`, `audit_service.py`, `notification_service.py`, `google.py`, `github.py`, `facebook.py`, `shutdown.py`, `test.py`

### Dependency Graph

```
Wave 1:  4A  4B  4D  4E  (all independent, parallel)
          │   │
Wave 2:  4A──→4C  (DI tracks needed for shootout wizard)
```

### Verification

- `just check` passes
- `just test-regression` passes
- `just test-golden-path` passes
- All API routers mounted and reachable (including signal_chain_groups)
- DI track upload → browse → playback works
- IR upload creates Gear + GearModel
- Shootout wizard creates shootouts end-to-end
- Comments appear on shootout detail page
- Tag, Preset, Block Type APIs respond correctly
- Custom error pages render (404, 500)
- Settings page shows connected providers
- Audit trail captures login events

### Key Files

| File | Action |
|------|--------|
| `apps/webapp/src/webapp/main.py` | Mount signal_chain_groups router, add exception handlers |
| `apps/webapp/src/webapp/api/v1/irs.py` | Create — IR upload endpoint |
| `apps/webapp/src/webapp/services/ir_upload_service.py` | Create — community IR upload service |
| `apps/webapp/src/webapp/services/asset_service.py` | Create — HMAC signed URLs, file serving |
| `apps/webapp/src/webapp/api/v1/files.py` | Create — secure file streaming |
| `apps/webapp/src/webapp/api/v1/tags.py` | Create — Tag CRUD API |
| `apps/webapp/src/webapp/services/tag_service.py` | Create — TagService |
| `apps/webapp/src/webapp/api/v1/presets.py` | Create — Preset CRUD API |
| `apps/webapp/src/webapp/services/preset_service.py` | Create — PresetService |
| `apps/webapp/src/webapp/api/v1/block_types.py` | Create — Block types API |
| `apps/webapp/src/webapp/exceptions.py` | Create — exception hierarchy |
| `apps/webapp/src/webapp/exception_handlers.py` | Create — exception handlers |
| `apps/webapp/src/webapp/services/audit_service.py` | Create — AuditService |
| `apps/webapp/src/webapp/services/notification_service.py` | Create — NotificationService |
| `apps/webapp/src/webapp/auth/providers/google.py` | Create — Google OAuth |
| `apps/webapp/src/webapp/auth/providers/github.py` | Create — GitHub OAuth |
| `apps/webapp/src/webapp/auth/providers/facebook.py` | Create — Facebook OAuth |
| `apps/webapp/src/webapp/shutdown.py` | Create — graceful shutdown |
| `frontend/astro/src/pages/404.astro` | Create — custom 404 page |
| `frontend/astro/src/pages/500.astro` | Create — custom 500 page |
| `frontend/astro/src/pages/fragments/shootouts/comments.html.ts` | Create — comments HTMX fragment |

### References

- [IMPLEMENTATION.md](../wiki/IMPLEMENTATION.md) — Phases 4A–4E
- [GTS-Technical-Architecture](../wiki/GTS-Technical-Architecture.md) — Architecture patterns
