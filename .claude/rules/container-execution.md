# Container-First Execution Rules

## Hard Constraints

- **All project code runs in Docker.** No host execution except E2E tests, worktree.py, and git/gh.
- **Use `just` commands.** Not raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- **Astro runs as a persistent service** (chokidar auto-rebuilds on source changes). Use `just build-astro` for explicit builds or `just watch-astro` for logs.

## Hot Reload — Never Restart Containers

Webapp and worker containers use **uvicorn --reload** with WatchFiles. Source edits on the host are detected automatically via bind mounts — the server process restarts within seconds. **Never run `docker compose restart`** for code changes. Just edit the file and wait.

## NEVER Run on Host

```bash
# FORBIDDEN - always use Docker equivalents via just
uv run pytest tests/unit/     # Use: just test-unit
uv run ruff check             # Use: just check-lint
uv run mypy                   # Use: just check-types
uv sync                       # Not needed
pytest                        # Use: just tdd <path>
pnpm build                    # Use: just build-astro
```

**The ONLY `uv run` on host is in `tests/e2e/python/` for E2E tests.**

For detailed execution matrix and script mapping, see the `docker-infra` skill.
