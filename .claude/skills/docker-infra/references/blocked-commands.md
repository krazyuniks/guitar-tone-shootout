# Blocked Commands & Safe Alternatives

## Hook-Blocked Commands

Even if you try, these are blocked by `block-volume-deletion.sh`:

| Category | Blocked Patterns |
|----------|------------------|
| Volume deletion | `docker volume rm`, `docker volume prune`, `down -v` |
| System pruning | `docker system prune`, `docker container prune` |
| Database destruction | `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb` |

## Safe Alternatives

| Need | Use This | NOT This |
|------|----------|----------|
| Start services | `just up-d` | `docker compose up -d` |
| Stop services | `just down` | `docker compose down` |
| Reset everything | Ask user to run `just reset` | `docker compose down -v` |
| Clean up worktree | `./worktree.py teardown <name>` | `docker volume rm ...` |
| Build frontend | `just build-astro` | `docker compose exec astro ...` |
| Fix permissions | `./worktree.py setup <name>` (idempotent) | `docker run --rm ... chown` |
| Clean orphans | `./worktree.py cleanup-orphans` | `docker system prune` |

## When Tooling Is Missing

1. Don't work around it
2. Ask: "Should I add a `./worktree.py <new-command>` for this?"
3. Or ask user to run the raw command manually

## Scenario: Need to recreate a volume

Tell the user:
1. Backup first: `./worktree.py db-backup`
2. Reset: Run `just reset` in your terminal (prompts for confirmation)
3. Restore: `./worktree.py db-restore`

## Scenario: Fix ANY infrastructure problem

`./worktree.py setup <name>` is idempotent -- fixes permissions, restarts services, rebuilds if needed, restores auth. Safe to run multiple times.
