# E95: Phase 4 Completion — DI Tracks, Groups, Shootout Workflow, Content APIs, Platform Infra

## Dependency Graph

```
T114 (unblocked)
T114 → T115
T115 → T116
T117 (unblocked)
T118 (unblocked)
T119 (unblocked)
T120 (unblocked)
T121 (unblocked)
T114 → T122
T123 (unblocked)
T124 (unblocked)
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
T137 (unblocked)
T137 → T138
T138 → T139
T124 → T140
T140 → T141
T139, T141 → T142
T114, T115, T116, T117, T118, T119, T120, T121, T122, T123, T124, T125, T126, T127, T128, T129, T130, T131, T132, T133, T134, T135, T136, T137, T138, T139, T140, T141, T142 → T143
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T114 | Custom Exception Hierarchy | complete | webapp | - |
| T115 | Exception Handlers + Content Negoti | complete | webapp | T114 |
| T116 | Error Pages (404/500 Astro + nginx  | complete | webapp | T115 |
| T117 | AuditService (Wire to Auth) | complete | webapp | - |
| T118 | UserNotification Model + Service +  | complete | webapp | - |
| T119 | Settings/Account Page | complete | webapp | - |
| T120 | Dynamic Sitemap.xml Endpoint | complete | webapp | - |
| T121 | Graceful Shutdown + Signal Handlers | complete | webapp | - |
| T122 | Test Error Endpoints (Dev-Mode Only | complete | webapp | T114 |
| T123 | Mount Signal Chain Groups Router +  | complete | webapp | - |
| T124 | Fix DI Track Frontend/API Contract  | complete | webapp | - |
| T125 | DI Track Browse Page (Pagination, W | complete | webapp | T124 |
| T126 | DI Track Upload UI (Drag-Drop, Prog | complete | webapp | T124 |
| T127 | Waveform + Audio Metadata Extractio | validating | webapp | - |
| T128 | IR Upload Endpoint + Service | pending | webapp | - |
| T129 | Asset/File Serving Service (HMAC Si | pending | webapp | - |
| T130 | Library DI Tracks Page (User Tracks | pending | webapp | T124, T129 |
| T131 | Tag CRUD API | pending | webapp | - |
| T132 | Preset CRUD API | pending | webapp | - |
| T133 | Block Types API | pending | webapp | - |
| T134 | Save/Remove Model UI + Model Counts | pending | webapp | - |
| T135 | Library Sorting, Filtering, Grid-Al | pending | webapp | - |
| T136 | License Text on Gear Detail Pages | pending | webapp | - |
| T137 | ShootoutComment Domain Entity + ORM | pending | core | - |
| T138 | Comments CRUD API | pending | webapp | T137 |
| T139 | Comments HTMX Fragment on Shootout  | pending | webapp | T138 |
| T140 | Wizard Step 2 — DI Track Selection  | pending | webapp | T124 |
| T141 | Wizard Step 3 — Review, Submit, Val | pending | webapp | T140 |
| T142 | Shootout Detail Page Enhancement | pending | webapp | T139, T141 |
| T143 | Full Regression + Golden Path | pending | - | T114, T115, T116, T117, T118, T119, T120, T121, T122, T123, T124, T125, T126, T127, T128, T129, T130, T131, T132, T133, T134, T135, T136, T137, T138, T139, T140, T141, T142 |

## Commands

```bash
python scripts/run_epic.py run 95   # Run TDD state machine
just epic-status 95                  # Check status
just debug E95                       # Debug issues
```
