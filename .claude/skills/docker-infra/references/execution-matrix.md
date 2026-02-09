# Execution Matrix

All project code runs in Docker. The ONLY host execution is E2E tests.

## Command Routing

| Component | Run Location | Command Pattern |
|-----------|--------------|-----------------|
| Webapp (Python) | Docker | `docker compose exec webapp <command>` |
| Frontend (Node/pnpm) | Docker (build profile) | `just build-astro` or `docker compose --profile build exec astro <command>` |
| Pipeline | Host | `cd pipeline && uv run <command>` |
| E2E Tests (Playwright) | Host | `just test-golden-path` |
| TDD Workflow Scripts | Host | `just epic-validate`, `just snapshot-verify`, etc. |
| Git/GitHub | Host | `git`, `gh` commands |

## Frontend Commands

Frontend container requires `--profile build` since it's not part of the runtime stack.

```bash
just build-astro     # Build Astro templates
just watch-astro     # Watch and auto-rebuild
just check-astro     # Lint + type check + build
```

## TDD Script Mapping

| Script | Just Command |
|--------|--------------|
| `snapshot_tests.py save` | `just tdd-lock <task>` |
| `snapshot_tests.py verify` | `just snapshot-verify <task>` |
| `snapshot_tests.py diff` | `just snapshot-diff <task>` |
| `snapshot_tests.py list` | `just snapshot-list` |
| `test_quality_check.py` | `just test-quality` |
| `health_check.py` | `just health <epic>` |
| `validate_tasks.py` | `just epic-validate <epic>` |
| `tasks_from_plan.py` | `just epic-materialise <epic>` |

## Starting Development

```bash
./worktree.py setup main   # First-time (idempotent)
just up-d                  # Start services
```

Entry point: http://localhost:9000
Runtime containers: db, redis, webapp, nginx, worker, scheduler
Build-only containers: astro (starts with `--profile build`)
