# Container-First Execution Rules

## Hard Constraints

- **All project code runs in Docker.** No host execution except E2E tests, worktree.py, and git/gh.
- **Use `just` commands.** Not raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- **Frontend needs `--profile build`.** Use `just build-astro` or `just watch-astro`.

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
