# Infrastructure Protection Rules

## Core Principle

**Use the provided tooling. Never run ad-hoc infrastructure commands.**

This project has declarative infrastructure management:
- `worktree.py` - Worktree lifecycle (setup, teardown, services)
- `just` commands - Day-to-day operations (up, down, build, check)
- `scripts/gts-admin` - Admin operations (sync, jobs, status)

**If you need to do something and there's no command for it:**
1. Ask the user if they want to add it to the tooling
2. Or ask the user to run the raw command manually
3. Do NOT run ad-hoc Docker/infrastructure commands yourself

## Why This Matters

Ad-hoc infrastructure commands are dangerous because:
1. **No guardrails** - Raw Docker commands don't know about project conventions
2. **No idempotency** - Scripts handle edge cases, raw commands don't
3. **No isolation** - A volume deletion in one context can affect another
4. **Irreversible** - Data cannot be recovered without backups

## Allowed vs Blocked

| Need | Use This | NOT This |
|------|----------|----------|
| Start services | `just up-d` | `docker compose up -d` |
| Stop services | `just down` | `docker compose down` |
| Reset everything | Ask user to run `just reset` | `docker compose down -v` |
| Clean up worktree | `./worktree.py teardown <name>` | `docker volume rm ...` |
| Build frontend | `just build-astro` | `docker compose exec astro ...` |
| Fix permissions | `./worktree.py setup <name>` (idempotent) | `docker run --rm ... chown` |

## Blocked Commands (Hook Enforced)

Even if you try, these will be blocked by `block-volume-deletion.sh`:

| Category | Blocked Patterns |
|----------|------------------|
| **Volume deletion** | `docker volume rm`, `docker volume prune`, `down -v` |
| **System pruning** | `docker system prune`, `docker container prune` |
| **Database destruction** | `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb` |

## What To Do Instead

### Scenario: Need to recreate a volume

**WRONG:**
```bash
docker compose down -v
docker volume rm gts-main-postgres
```

**RIGHT:**
```markdown
The database volume has corrupt data. To fix this:

1. Backup first: `./worktree.py db-backup`
2. Reset: Run `just reset` in your terminal (this will prompt for confirmation)
3. Restore: `./worktree.py db-restore`

Would you like me to add a `./worktree.py db-reset` command to handle this?
```

### Scenario: Need to fix file permissions / container issues / anything

**WRONG:**
```bash
docker run --rm -v /path:/data alpine chown -R 1000:1000 /data
docker volume rm old-volume
docker compose up -d
```

**RIGHT:**
```bash
# worktree.py setup is IDEMPOTENT - run it for ANY infrastructure issue
./worktree.py setup main
```

**`./worktree.py setup` is the answer to most infrastructure problems.** It:
- Fixes permissions
- Restarts services
- Rebuilds if needed
- Restores auth
- Is safe to run multiple times

### Scenario: Cleanup orphaned containers/volumes

**WRONG:**
```bash
docker system prune -af
docker volume prune -f
```

**RIGHT:**
```bash
# Use the provided cleanup command
./worktree.py cleanup-orphans
```

## If Tooling Is Missing

If you need to do something and there's no command for it:

1. **Don't work around it** - That's how data gets deleted
2. **Ask:** "Should I add a `./worktree.py <new-command>` for this?"
3. **Or ask user to run manually:** "Please run `<raw command>` in your terminal"

## Related

- `.claude/hooks/block-volume-deletion.sh` - Enforcement hook
- `AGENTS.md` - Rule #7: Use provided tooling
- `.claude/rules/no-workarounds.md` - No shortcuts or deviations
- `.claude/rules/container-execution.md` - Container-first execution
