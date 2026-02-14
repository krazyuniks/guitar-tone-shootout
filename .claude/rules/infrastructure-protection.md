<!-- domains: infrastructure -->
# Infrastructure Protection Rules
- NEVER run ad-hoc Docker commands. Use `just` + `worktree.py`.
- NEVER edit `docker-compose.override.yml` or `.env.local` -- they are auto-generated.
- Hook-blocked commands: `docker volume rm`, `docker volume prune`, `down -v`, `docker system prune`, `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb`.
- For ANY infrastructure problem: `./worktree.py setup <name>` (idempotent).
