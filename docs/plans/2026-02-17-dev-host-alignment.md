# Dev Environment Alignment — Host ↔ Docker

> **For Claude:** Continue this work on branch `feat/t3k-login-auto-refresh`. Read this file for context, then work through the items below.

**Goal:** Eliminate all divergence between host and Docker development environments. Single source of truth for every tool version. No graceful fallbacks.

**Principle:** Idempotent, declarative, deterministic. If Docker isn't running, fail hard.

---

## Completed (previous session)

- Unified storage bind mount: `../gts-storage:/app/storage` with `GTS_STORAGE_ROOT`
- Pre-commit ruff hooks now run inside Docker (see `scripts/ruff-hook.sh`)
- Host-only code (worktree/, workflow/) uses `uvx ruff@{version}` with version from pyproject.toml
- Removed `:ro` flags from webapp volume mounts (ruff can now write)
- Pinned `ruff==0.15.1` in pyproject.toml
- Removed graceful fallback from astro-lint.sh

## Open Items (fix in this session)

### 1. Astro check trailing whitespace loop (BLOCKING)

`astro check` (run by pre-commit via `scripts/astro-lint.sh`) regenerates `frontend/astro/.astro/*.{d.ts,mjs}` files every time. These generated files have trailing whitespace that the `trailing-whitespace` and `end-of-file-fixer` hooks fix. On next run, astro check regenerates again. Infinite loop.

**Options:**
- Add `.astro/` to `.gitignore` (if generated files shouldn't be committed)
- Configure astro to not regenerate on `check`
- Exclude `.astro/` from whitespace hooks (last resort)
- Fix astro's code generation to not emit trailing whitespace (upstream)

### 2. Pin ALL Python dependency versions

`pyproject.toml` uses `>=` for most deps. Pin exact versions (`==`) for all packages. Use `uv` equivalent of `npm-check-updates` to manage upgrades.

Research: `uv lock --upgrade` updates all packages to latest compatible versions. The lock file IS the pin. Consider whether `==` in pyproject.toml is needed if uv.lock is committed and `--frozen` is used in Dockerfiles.

### 3. Host Python version alignment

Pyright MCP runs on host Python but the project uses Python 3.14 in Docker. Host may have different Python version, causing false Pyright errors (e.g. `StrEnum` not found).

**Fix:** Install Python 3.14 on host via `uv python install 3.14` and configure Pyright to use it.

### 4. Node/pnpm version alignment

Check if `frontend/astro/package.json` has `engines` field pinning node/pnpm versions. If not, add them. Ensure Docker astro service uses same versions.

### 5. Update ALL Docker base images to latest

Check all Dockerfiles in `infrastructure/docker/` for base image versions. Update to latest stable.

### 6. Model backfill for source_downloads

The 4,778 models in `../gts-storage/models/` were archive-imported and don't have corresponding entries in `source_downloads/t3k/{model_id}/`. When T3K sync runs, it will re-download these (wasting bandwidth + disk).

**Fix:** Write a script that queries the database to map `core_uuid` → `t3k_model_id`, then creates symlinks or empty marker files in `source_downloads/t3k/{model_id}/{filename}.nam` so the downloader's `path.exists()` check passes.

### 7. Fix 28 pre-existing test failures

`test_audio_job.py`, `test_master_audio.py`, `test_shootout_orchestrator.py` all fail with `'Job' object has no attribute 'signal_chain'`. These are from epic-112 work and were pre-existing on main. They need to be fixed.

---

## Key Files

- `.pre-commit-config.yaml` — pre-commit config (local hooks, no external repos for ruff)
- `scripts/ruff-hook.sh` — routes Python files to Docker or host ruff
- `scripts/astro-lint.sh` — runs astro check in Docker
- `pyproject.toml` — ruff version pin, all Python deps
- `docker-compose.yml` — webapp volumes (now RW), service configs
- `uv.lock` — locked dependency versions
