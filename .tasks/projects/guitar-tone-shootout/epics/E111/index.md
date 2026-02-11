# E111: Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer

## Dependency Graph

```
T112 (unblocked)
T113 (unblocked)
T114 (unblocked)
T112, T113 → T115
T116 (unblocked)
T117 (unblocked)
T112, T116, T117 → T118
T114, T115, T116 → T119
T115 → T120
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T112 | Worker dual database session factor | complete | worker | - |
| T113 | Worker container orchestration — ru | complete | worker | - |
| T114 | T3K oauth_tokens Alembic migration | complete | source-t3k | - |
| T115 | Admin API — enqueue, source dashboa | pending | worker | T112, T113 |
| T116 | Interleaved backfill+newest sync lo | complete | source-t3k | - |
| T117 | Model file download service | pending | - | - |
| T118 | pgmq consumer and GearMapperService | pending | worker | T112, T116, T117 |
| T119 | Scheduler tasks — SOURCE_SYNC handl | pending | worker | T114, T115, T116 |
| T120 | gts-admin CLI and just admin regist | pending | - | T115 |

## Commands

```bash
python scripts/run_epic.py run 111   # Run TDD state machine
just epic-status 111                  # Check status
just debug E111                       # Debug issues
```
