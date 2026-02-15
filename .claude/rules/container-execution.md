<!-- domains: infrastructure -->
# Container-First Execution Rules
- All project code runs in Docker. Host exceptions: E2E tests, `worktree.py`, git/gh.
- Use `just` commands. Never raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- Astro runs as a persistent service (chokidar auto-rebuilds). Use `just build-astro` or `just watch-astro`.
- Never restart containers for code changes. Uvicorn `--reload` with WatchFiles detects edits automatically.
- The ONLY `uv run` on host is in `tests/e2e/python/` for E2E tests.
