# Dev Environment Alignment — Host ↔ Docker

> **For Claude:** Continue this work on branch `feat/t3k-login-auto-refresh`. Read this file for context, then work through the remaining items below.

**Goal:** Eliminate all divergence between host and Docker development environments. Single source of truth for every tool version. No graceful fallbacks.

**Principle:** Idempotent, declarative, deterministic. If Docker isn't running, fail hard.

---

## Completed

### Previous session (2026-02-17 morning)
- Unified storage bind mount: `../gts-storage:/app/storage` with `GTS_STORAGE_ROOT`
- Pre-commit ruff hooks now run inside Docker (see `scripts/ruff-hook.sh`)
- Host-only code (worktree/, workflow/) uses `uvx ruff@{version}` with version from pyproject.toml
- Removed `:ro` flags from webapp volume mounts (ruff can now write)
- Pinned `ruff==0.15.1` in pyproject.toml
- Removed graceful fallback from astro-lint.sh

### This session (2026-02-17 afternoon)
1. **Astro whitespace loop** — gitignored `frontend/astro/.astro/`, removed from tracking
2. **Python dep pinning** — `uv.lock` + `--frozen` is sufficient, no `==` pins needed
3. **Host Python alignment** — switched from pyenv to uv-only, Python 3.14.3 everywhere:
   - Host: uv manages `~/.local/bin/python3` → 3.14.3
   - Docker: pinned `python:3.14.3-slim` in all Dockerfiles
   - Pyright: `[tool.pyright] pythonVersion = "3.14"` in pyproject.toml
   - mypy: updated `python_version` from 3.12 to 3.14
   - Removed pyenv from dotfiles (`~/.dotfiles/source/01_path.sh`, `~/.dotfiles/init/10_runtimes.sh`)
4. **Node/pnpm alignment** — added `engines` to package.json, pinned `node:24.13.1-alpine`
5. **Docker base images** — all Dockerfiles pinned to exact versions
6. **Model backfill** — restored DB from backup, ran archive sync (6,212 tones, 31,548 models, 496 NAM files)
7. **Update script** — created `scripts/update.sh` for periodic dependency updates

## Remaining

### 7. Fix 28 pre-existing test failures

`test_audio_job.py`, `test_master_audio.py`, `test_shootout_orchestrator.py` all fail because tests mock `session.execute` returning the wrong object type (returns `Job` instead of `ShootoutChain` on second query). Tests also use `unittest.mock` which is banned by project policy.

**Fix:** Rewrite these 28 tests with real DB fixtures (SQLite in-memory or test PostgreSQL), following the project's no-mock testing policy. The production code in `worker/jobs/audio.py` is correct — only the tests are broken.

### 8. Backup automation (NEW)

`worktree.py setup` needs to backup and restore ALL databases (gts_core + gts_t3k_source + any future source DBs). Requirements:
- Modularise backup/restore in `worktree.py` so it can be called from CLI independently
- Schedule twice-daily automatic backups (via scheduler or cron)
- Use same backup method for both `worktree.py setup` and standalone backup
- Backup all databases, not just gts_core

---

## Key Files

- `.pre-commit-config.yaml` — pre-commit config
- `scripts/ruff-hook.sh` — routes Python files to Docker or host ruff
- `scripts/astro-lint.sh` — runs astro check in Docker
- `scripts/update.sh` — periodic dependency update script
- `pyproject.toml` — tool versions, Pyright config, mypy config
- `docker-compose.yml` — service configs
- `uv.lock` — locked dependency versions
- `.python-version` — uv Python pin (3.14.3)
