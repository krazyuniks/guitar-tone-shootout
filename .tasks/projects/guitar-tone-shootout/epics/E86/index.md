# E86: E86 — Phase 4 Remainder

## Dependency Graph

```
T87 (unblocked)
T87 -> T88
T89 (unblocked)
T89 -> T90
T90 -> T91
T92 (unblocked)
T93 (unblocked)
T93 -> T94
T93, T94 -> T95
T88 -> T96
T96 -> T97
T94 -> T98
T90 -> T99
T91, T92, T95, T97, T98, T99 -> T100
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T87 | UserGear FK Migration — Domain + ORM + A | pending | webapp | - |
| T88 | Fix UserGear FK Downstream Consumers | pending | webapp | T87 |
| T89 | DI Track Upload Endpoint | pending | webapp | - |
| T90 | DI Track Stream Endpoint | pending | webapp | T89 |
| T91 | DI Track Audio Player UI | pending | frontend | T90 |
| T92 | DI Track Seed Import Command | pending | scripts | - |
| T93 | SignalChainGroupService + CRUD API | pending | webapp | - |
| T94 | Permutation Batch Generation | pending | webapp | T93 |
| T95 | Signal Chain Group Management UI | pending | frontend | T93, T94 |
| T96 | Model-Level Gear Library Management API | pending | webapp | T88 |
| T97 | Gear Detail Page with Model Listing + Li | pending | frontend | T96 |
| T98 | Wizard Chain Selection from Groups | pending | webapp | T94 |
| T99 | Shootout Detail Page Pre-Processing Stat | pending | frontend | T90 |
| T100 | Regression Test Updates for All New Endp | pending | testing | T91, T92, T95, T97, T98, T99 |

## Commands

```bash
python scripts/run_epic.py run 86   # Run TDD state machine
python scripts/run_epic.py status 86 # Check status
```
