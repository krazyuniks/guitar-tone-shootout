# E95: Phase 4 Completion — DI Tracks, Groups, Shootout Workflow, Content APIs, Platform Infra

## Prerequisites

| Requirement | Status | Verification |
|-------------|--------|--------------|
| Auth tokens | Valid | `./worktree.py auth-status` |
| Services | db, webapp, nginx, astro healthy | `just health` |
| Chrome DevTools MCP | Required for UI tasks | Verify at session start |
| Playwright MCP | Required for E2E/wizard tasks | Verify at session start |

**Gate:** Implementation sessions MUST verify MCP availability before starting UI/E2E tasks. Exit if unavailable.

## Prior Work (E86 + E94 — Already Complete)

E86 delivered: DI track upload/stream/player/seed, signal chain group CRUD/batch/UI, model-level gear library, gear detail with models, wizard chain selection from groups, shootout detail pre-processing.

E94 delivered: Worker/scheduler/T3K infrastructure (Phase 5A/5B/5C).

This epic addresses all remaining gaps.

## Dependency Graph

```
T114 → T115 → T116
T114 → T122
T117 (unblocked)
T118 (unblocked)
T119 (unblocked)
T120 (unblocked)
T121 (unblocked)
T123 (unblocked)
T124 → T125
T124 → T126
T127 (unblocked)
T128 (unblocked)
T129 (unblocked)
T124, T129 → T130
T131 (unblocked)
T132 (unblocked)
T133 (unblocked)
T134 (unblocked)
T135 (unblocked)
T136 (unblocked)
T137 → T138 → T139
T124 → T140 → T141
T139, T141 → T142
T142, T136, T135, T133, T130, T123, T122, T121, T120, T119 → T143
```

## Execution Order (Sequential)

### Wave 1: Platform Infrastructure (4E) — Foundation

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T114 | Custom Exception Hierarchy | webapp | - | - |
| T115 | Exception Handlers + Content Negotiation | webapp | - | T114 |
| T116 | Error Pages (404/500 Astro + nginx 502/503/504) | webapp | Chrome | T115 |
| T117 | AuditService (model exists, wire to auth) | webapp | - | - |
| T118 | UserNotification Model + Service + API | webapp | - | - |
| T119 | Settings/Account Page | webapp | Chrome | - |
| T120 | Dynamic Sitemap.xml Endpoint | webapp | - | - |
| T121 | Graceful Shutdown + Signal Handlers | webapp | - | - |
| T122 | Test Error Endpoints (dev-mode only) | webapp | - | T114 |

### Wave 2: Signal Chain Groups (4B) — Quick Fix

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T123 | Mount Signal Chain Groups Router + Verify | webapp | Chrome | - |

### Wave 3: DI Track & IR Upload (4A)

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T124 | Fix DI Track Frontend/API Contract Mismatch | webapp | Chrome | - |
| T125 | DI Track Browse Page (pagination, waveforms) | webapp | Chrome | T124 |
| T126 | DI Track Upload UI (drag-drop, progress, metadata) | webapp | Chrome+PW | T124 |
| T127 | Waveform + Audio Metadata Extraction on Upload | webapp | - | - |
| T128 | IR Upload Endpoint + Service | webapp | - | - |
| T129 | Asset/File Serving Service (HMAC signed URLs) | webapp | - | - |
| T130 | Library DI Tracks Page (user tracks + delete) | webapp | Chrome | T124, T129 |

### Wave 4: Library, Gear & Content APIs (4D)

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T131 | Tag CRUD API | webapp | - | - |
| T132 | Preset CRUD API | webapp | - | - |
| T133 | Block Types API | webapp | - | - |
| T134 | Save/Remove Model UI + Model Counts + Download Status | webapp | Chrome | - |
| T135 | Library Sorting, Filtering, Grid-Aligned Pagination | webapp | Chrome | - |
| T136 | License Text on Gear Detail Pages | webapp | Chrome | - |

### Wave 5: Shootout Workflow (4C) — Depends on 4A + 4B

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T137 | ShootoutComment Domain Entity + ORM Model + Migration | core | - | - |
| T138 | Comments CRUD API | webapp | - | T137 |
| T139 | Comments HTMX Fragment on Shootout Detail | webapp | Chrome | T138 |
| T140 | Wizard Step 2 — DI Track Selection Modal | webapp | Chrome+PW | T124 |
| T141 | Wizard Step 3 — Review, Submit, Validation | webapp | Chrome+PW | T140 |
| T142 | Shootout Detail Page Enhancement | webapp | Chrome | T139, T141 |

### Wave 6: Final Verification

| Task | Title | Project | MCP | Blocked By |
|------|-------|---------|-----|------------|
| T143 | Full Regression + Golden Path | - | PW | all previous |

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T114 | Custom Exception Hierarchy | pending | webapp | - |
| T115 | Exception Handlers + Content Negotiation | pending | webapp | T114 |
| T116 | Error Pages (404/500 + nginx) | pending | webapp | T115 |
| T117 | AuditService (wire to auth) | pending | webapp | - |
| T118 | UserNotification Model + Service + API | pending | webapp | - |
| T119 | Settings/Account Page | pending | webapp | - |
| T120 | Dynamic Sitemap.xml Endpoint | pending | webapp | - |
| T121 | Graceful Shutdown + Signal Handlers | pending | webapp | - |
| T122 | Test Error Endpoints (dev-mode only) | pending | webapp | T114 |
| T123 | Mount Signal Chain Groups Router | pending | webapp | - |
| T124 | Fix DI Track Frontend/API Contract | pending | webapp | - |
| T125 | DI Track Browse Page | pending | webapp | T124 |
| T126 | DI Track Upload UI | pending | webapp | T124 |
| T127 | Waveform + Audio Metadata Extraction | pending | webapp | - |
| T128 | IR Upload Endpoint + Service | pending | webapp | - |
| T129 | Asset/File Serving Service | pending | webapp | - |
| T130 | Library DI Tracks Page | pending | webapp | T124, T129 |
| T131 | Tag CRUD API | pending | webapp | - |
| T132 | Preset CRUD API | pending | webapp | - |
| T133 | Block Types API | pending | webapp | - |
| T134 | Save/Remove Model UI + Counts + Status | pending | webapp | - |
| T135 | Library Sorting/Filtering/Pagination | pending | webapp | - |
| T136 | License Text on Gear Detail | pending | webapp | - |
| T137 | ShootoutComment Entity + Model + Migration | pending | core | - |
| T138 | Comments CRUD API | pending | webapp | T137 |
| T139 | Comments HTMX Fragment | pending | webapp | T138 |
| T140 | Wizard Step 2 — DI Track Selection | pending | webapp | T124 |
| T141 | Wizard Step 3 — Review + Submit | pending | webapp | T140 |
| T142 | Shootout Detail Page Enhancement | pending | webapp | T139, T141 |
| T143 | Full Regression + Golden Path | pending | - | all |

## Known Issues to Address

1. **Signal chain groups router not mounted** — `signal_chain_groups` imported but not included in `main.py` (T123)
2. **DI track contract mismatch** — Frontend posts to `/api/v1/di-tracks/upload` with `title`/`pickups` fields; API expects `POST /api/v1/di-tracks` with `name`/`pickup` (T124)
3. **Frontend `tuning` field** — Upload form has `tuning` field not in API; decide: add to API or remove from form (T124)

## What Already Exists (Do Not Recreate)

| Artifact | Location |
|----------|----------|
| AuditLog ORM model | `models/job.py:163` |
| AuditRepository | `repositories/audit_repository.py` |
| DITrack entity + model + repo + service | Complete CRUD |
| SignalChainGroupService + API + schemas | Complete CRUD (E86 T93) |
| BlockTypeRegistry | `services/block_type_registry.py` |
| PresetService | `services/preset_service.py` |
| Preset ORM model | `models/preset.py` |
| BlockType ORM model | `models/block_type.py` |
| Shootout comments template | `fragments/shootouts/comments.html.ts` |
| Wizard step templates | `fragments/shootouts/create/step1-3.html.ts` |
| Settings page template | `pages/settings_account.html.ts` |
| DI track browse template | `fragments/di-tracks/public_browse.html.ts` |
| Library group templates | `fragments/library/groups.html.ts`, `group_detail.html.ts` |

## Commands

```bash
python scripts/run_epic.py run 95   # Run TDD state machine
just epic-status 95                  # Check status
just debug E95                       # Debug issues
```
