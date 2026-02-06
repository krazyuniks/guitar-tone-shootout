# GTS Ralph Hybrid Customizations

## Backpressure Hooks

Post-iteration verification at `.ralph-hybrid/hooks/post_iteration.sh`:
- Runs `ruff check` and `ruff format --check` for linting
- Runs `mypy` for type checking (non-blocking)
- Runs `pytest` for unit and integration tests
- Returns exit code 75 (VERIFICATION_FAILED) on failure
- Auto-detects Docker vs host execution

```bash
# Test the hook
.ralph-hybrid/hooks/post_iteration.sh context.json --dry-run
```

## Project Memories

Cross-session learning at `.ralph-hybrid/memories.md`:

| Section | Purpose |
|---------|---------|
| **Patterns** | Astro + Jinja2 rendering, transaction handling, testing patterns, container rules |
| **Decisions** | PostgreSQL/SQLAlchemy, pre-bundled Astro, worktrees, Python Playwright |
| **Fixes** | Navigation issues, E2E test fixes, auth centralization |
| **Context** | Domain concepts (shootouts, signal chains, gear, auth patterns) |

Memories are automatically injected into each iteration prompt.
