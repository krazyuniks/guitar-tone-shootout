# E70: Epic: Video BC Integration — Remotion-Powered Composition

## Dependency Graph

```
T71 (unblocked)
T71 → T72
T72 → T73
T73 → T74
T74 → T75
T75, T83 → T76
T72 → T77
T72 → T78
T73 → T80
T74 → T81
T74 → T82
T71 → T83
T76 → T84
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T71 | Phase 1: Core Domain — Generic Comp | complete | core | - |
| T72 | Phase 2: libs/video/ Scaffold + Aud | complete | audio | T71 |
| T73 | Phase 3: Docker Integration — Video | complete | - | T72 |
| T74 | Phase 4: Video BC — Python Implemen | complete | - | T73 |
| T75 | Phase 5: Video BC — Remotion Compon | complete | - | T74 |
| T76 | Phase 6b: Worker Integration — Vide | pending | worker | T75, T83 |
| T77 | Phase 7: Frontend — Remotion Player | complete | - | T72 |
| T78 | Phase 8: Tooling & Just Commands | complete | - | T72 |
| T80 | Phase 9: worktree.py — Video Servic | complete | - | T73 |
| T81 | Phase 10: Documentation — Update DE | complete | - | T74 |
| T82 | Phase 11: .claude Skills/Agents — V | pending | - | T74 |
| T83 | Phase 6a: Alembic Migration — Shoot | pending | webapp | T71 |
| T84 | Phase 12: Integration Test — End-to | pending | - | T76 |

## Commands

```bash
python scripts/run_epic.py run 70   # Run TDD state machine
just epic-status 70                  # Check status
just debug E70                       # Debug issues
```
