<!-- domains: infrastructure -->
# Container-First Execution Rules
- All project code runs in Docker. Host exceptions: E2E tests, the `worktree` engine CLI, git/gh.
- Use `just` commands. Never raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- Astro runs as a persistent service (chokidar auto-rebuilds). Use `just build-astro` or `just watch-astro`.
- Never restart containers for code changes. Uvicorn `--reload` with WatchFiles detects edits automatically.
- The ONLY `uv run` on host is in `tests/e2e/python/` for E2E tests.
- **Main-only services:** t3k-sync, audio-worker, and video-worker run ONLY on the `main` stack (`--profile jobs` is activated when `basename $(pwd) == main`). A feature worktree's engine-provisioned stack runs webapp + db (+ astro, which builds dist); nginx and the jobs workers are main-only. Database, external API sync, file downloads, and job queues are singletons — main is the source of truth. Never duplicate these services across worktrees.
