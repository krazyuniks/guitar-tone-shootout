# E33: refactor: convert all selectinload to joinedload for single-query aggregate hydration

## Dependency Graph

```
T34 (unblocked)
T34 → T35
T35 → T36
T34 → T37
T37 → T38
T34 → T39
T34 → T40
T40 → T41
T42 (unblocked)
T42 → T43
T42 → T44
T42 → T45
T43 → T46
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
| T34 | [Task]: A1 - Convert all ORM relati | complete | webapp | - |
| T35 | [Task]: B1 - Convert GearRepository | complete | webapp | T34 |
| T36 | [Task]: B2 - Convert GearRepository | complete | webapp | T35 |
| T37 | [Task]: C1 - Convert UserRepository | complete | webapp | T34 |
| T38 | [Task]: C2 - Refactor UserRepositor | complete | webapp | T37 |
| T39 | [Task]: D1 - Convert SignalChainRep | complete | webapp | T34 |
| T40 | [Task]: E1 - Convert ShootoutReposi | complete | webapp | T34 |
| T41 | [Task]: E2 - Convert ShootoutReposi | complete | webapp | T40 |
| T42 | [Task]: F1 - Add query counting fix | complete | webapp | - |
| T43 | [Task]: F2 - Add integration tests  | complete | webapp | T42 |
| T44 | [Task]: F3 - Add integration tests  | locked | webapp | T42 |
| T45 | [Task]: F4 - Add integration tests  | pending | webapp | T42 |
| T46 | [Task]: G1 - Verify regression and  | pending | webapp | T43 |

## Commands

```bash
python scripts/run_epic.py run 33   # Run TDD state machine
just epic-status 33                  # Check status
just debug E33                       # Debug issues
```
