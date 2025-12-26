# Session State

**Last Updated:** 2025-12-26
**Branch:** main

---

## Project Pivot Summary

This project is pivoting from a CLI-focused tool to a **full web application** with:
- Tone 3000 OAuth integration for user authentication
- PostgreSQL database for shootout storage
- Job queue for async pipeline processing
- Astro + React frontend (replacing Flask + HTMX)

See `EXECUTION-PLAN.md` for full architecture and epic tracking.

---

## Active Work

| Epic | Issue | Dev Docs | Status | Next Action |
|------|-------|----------|--------|-------------|
| Web Application Foundation | #5 | `dev/active/web-app-foundation/` | In Progress | #7 merged, start #8 |

---

## Epic Overview

| Milestone | Epic Issue | Sub-Issues | Status |
|-----------|------------|------------|--------|
| v2.0 - Web Application Foundation | #5 | #6, #7, #8, #9, #10 | In Progress |
| v2.1 - Tone 3000 Integration | #11 | #12, #13 | Blocked by v2.0 |
| v2.2 - Job Queue System | #14 | #15, #16, #17 | Blocked by v2.0 |
| v2.3 - Frontend (Astro) | #18 | #19, #20, #21 | Blocked by v2.0 |
| v2.4 - Pipeline Web Adapter | #22 | #23, #24, #25 | Blocked by v2.0 |

---

## Execution Order

```
v2.0 Foundation → v2.1 Tone3000 → v2.2 Jobs → v2.3 Frontend → v2.4 Pipeline
     │                 │              │             │              │
     │                 └──────────────┴─────────────┴──────────────┘
     │                           (can run in parallel after v2.0)
     ▼
Next: Issue #8 (after #7 merges)
```

---

## Quick Commands

```bash
# View all open issues
gh issue list --state open

# View specific milestone
gh issue list --milestone "v2.0 - Web Application Foundation"

# View issue details
gh issue view 6

# Read current dev-docs
cat dev/active/web-app-foundation/web-app-foundation-context.md
```

---

## Recent Activity

- **2025-12-26**: Created #7 Docker Compose production environment. Multi-stage builds, nginx reverse proxy, gunicorn workers, health checks, resource limits.
- **2025-12-26**: Fixed Tailwind CSS v4 compatibility (migrated from @astrojs/tailwind to @tailwindcss/vite).
- **2025-12-26**: Merged #6. Set up Git workflow (squash-only, ff-only). Added admin.sh for dependency management.
- **2025-12-26**: Completed #6 Docker Compose dev environment. Backend + frontend + db + redis all running with hot-reload.
- **2025-12-26**: Project pivot decided. Created epics #5-#25. Closed old issues #1-4.
- **2025-12-26**: Set up dev-docs framework to prevent context loss.

---

## Resume Instructions

1. Read this file first
2. Check `EXECUTION-PLAN.md` for architecture decisions
3. Read active task docs in `dev/active/[task]/`
4. Continue with the "Next Action" from the table above
