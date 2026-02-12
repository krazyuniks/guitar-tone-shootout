# E111: Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer

## Dependency Graph

```
T112 ✅  T114 ✅
  │         │
  ├─────────┤
  ▼         │
T113 ──────►T118 ──────► (data flows)
  │         │
  │    T117─┘
  │
  ▼
T115 ──────► T120 ✅
  │
T119
```

- **Wave 1 (parallel):** T113 (wire consumer), T117 (integrate downloader)
- **Wave 2 (parallel):** T115 (admin endpoints), T118 (fix bugs + verify)
- **Wave 3:** T119 (scheduler verification)

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T112 | Worker dual database session factory | complete | worker | - |
| T113 | Wire real pgmq consumer in entrypoint | pending | worker | - |
| T114 | T3K oauth_tokens Alembic migration | complete | source-t3k | - |
| T115 | Implement admin sync endpoints (replace stubs) | pending | worker | T112, T113 |
| T117 | Integrate model downloader into sync loop | pending | source-t3k | - |
| T118 | Fix consumer bugs and verify e2e data flow | pending | worker | T112, T113, T117 |
| T119 | Verify scheduler dispatches sync end-to-end | pending | worker | T114, T115 |
| T120 | gts-admin CLI and just admin registration | complete | tooling | T115 |

## Commands

```bash
python scripts/run_epic.py run 111   # Run TDD state machine
just epic-status 111                  # Check status
just debug E111                       # Debug issues
```
