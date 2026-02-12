# E111: Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer

## Dependency Graph

```
T112 (unblocked)
T113 (unblocked)
T114 (unblocked)
T112, T113 → T115
T117 (unblocked)
T112, T113, T117 → T118
T114, T115 → T119
T115 → T120
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T112 | Worker dual database session factor | complete | worker | - |
| T113 | Wire real pgmq consumer in entrypoi | complete | worker | - |
| T114 | T3K oauth_tokens Alembic migration | complete | - | - |
| T115 | Implement admin sync endpoints (rep | complete | worker | T112, T113 |
| T117 | Integrate model downloader into syn | complete | - | - |
| T118 | Fix consumer bugs and verify end-to | complete | worker | T112, T113, T117 |
| T119 | Verify scheduler dispatches sync en | validating | worker | T114, T115 |
| T120 | gts-admin CLI and just admin regist | complete | - | T115 |

## Commands

```bash
python scripts/run_epic.py run 111   # Run TDD state machine
just epic-status 111                  # Check status
just debug E111                       # Debug issues
```
