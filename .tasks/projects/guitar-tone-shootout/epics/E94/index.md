# E94: E94 — Phase 5A/5B/5C Job System, T3K Source Adapter, Shootout Audio

## Dependency Graph

```
T99 → T100
T99 → T101
T100 → T102
T100, T101, T102 → T103
T99, T100 → T104
T105 (unblocked)
T105, T96 → T106
T107 (unblocked)
T107, T96 → T108
T108, T106 → T109
T109 → T110
T110 → T111
T97, T98 → T112
T112, T111, T103, T104 → T113
T95 (unblocked)
T95 → T96
T95 → T97
T96, T97 → T98
T99 (unblocked)
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T100 | T3K Staging Tables + Alembic Migrat | complete | t3k | T99 |
| T101 | T3K API Client + Rate Limiting | complete | t3k | T99 |
| T102 | T3K OAuth Token Management | pending | t3k | T100 |
| T103 | T3K Sync Service — Backfill + Newes | pending | t3k | T100, T101, T102 |
| T104 | GearSyncRecord pgmq Publisher | pending | t3k | T99, T100 |
| T105 | Extend JobType Enum + Shootout Job  | complete | core | - |
| T106 | Shootout Processing Orchestrator Jo | pending | worker | T105, T96 |
| T107 | Scheduler Redis Broker + Distribute | complete | scheduler | - |
| T108 | Scheduled Tasks — Stale Job Monitor | pending | scheduler | T107, T96 |
| T109 | Per-Chain Audio Processing Job Hand | pending | worker | T108, T106 |
| T110 | Loudness Normalisation + Master Aud | pending | worker | T109 |
| T111 | Processing Trigger Endpoint | pending | webapp | T110 |
| T112 | WebSocket Job Progress Endpoint | pending | webapp | T97, T98 |
| T113 | Integration Smoke Test + Quality Ga | pending | worker | T112, T111, T103, T104 |
| T95 | Worker Redis Broker + Settings | complete | worker | - |
| T96 | Worker Database Session Factory | complete | worker | T95 |
| T97 | Worker Admin API Scaffold | complete | worker | T95 |
| T98 | Admin API Job Management Endpoints | pending | worker | T96, T97 |
| T99 | T3K Domain Model | complete | t3k | - |

## Commands

```bash
python scripts/run_epic.py run 94   # Run TDD state machine
just epic-status 94                  # Check status
just debug E94                       # Debug issues
```
