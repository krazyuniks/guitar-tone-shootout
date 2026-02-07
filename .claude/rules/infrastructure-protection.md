# Infrastructure Protection Rules

## Hard Constraints

- **NEVER run ad-hoc Docker commands.** Use `just` + `worktree.py`.
- **NEVER edit `docker-compose.override.yml` or `.env.local`** — they are auto-generated.
- **Hook-blocked commands:** `docker volume rm`, `docker volume prune`, `down -v`, `docker system prune`, `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb`.
- **For ANY infrastructure problem:** `./worktree.py setup <name>` (idempotent — fixes permissions, restarts, rebuilds, restores auth).

## If Tooling Is Missing

1. Don't work around it
2. Ask: "Should I add a `./worktree.py <new-command>` for this?"
3. Or ask user to run the raw command manually

For detailed blocked commands list and safe alternatives, see the `docker-infra` skill.
