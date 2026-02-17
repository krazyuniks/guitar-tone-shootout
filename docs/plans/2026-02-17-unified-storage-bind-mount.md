# Unified Storage Bind Mount Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace per-worktree Docker named volumes (`upload_data`, `processed_data`) with a single shared bind mount (`../gts-storage:/app/storage`) matching the architecture spec.

**Architecture:** All file storage (models, uploads, audio, videos, source downloads) lives under one host directory `../gts-storage/` bind-mounted into containers at `/app/storage`. A single env var `GTS_STORAGE_ROOT` (no default fallback) drives all path resolution. No hardcoded paths anywhere in application code.

**Tech Stack:** Docker Compose, Python (FastAPI worker/webapp), worktree.py (SQLite registry)

---

## Pre-flight: Current State

**Named volumes being replaced:**
- `gts-uploads-${GTS_WORKTREE:-main}` → mounted at `/app/uploads` (currently empty)
- `gts-processed-${GTS_WORKTREE:-main}` → mounted at `/app/processed` (1.7GB live data)

**Bind mount directory (already exists):**
- `../gts-storage/` — has stale archive data + `.gitignore`

**Live data in `gts-processed-main` volume:**
- `models/` — 4,778 files (`{core_uuid}.nam`)
- `source_downloads/t3k/` — 10,497 dirs (`{model_id}/{url_filename}.nam`)
- `shootouts/` — empty dir

**Target layout on host (`../gts-storage/`):**
```
../gts-storage/
├── models/                    # {core_uuid}.nam
├── uploads/
│   ├── di_tracks/            # {user_id}/{uuid}.{ext}
│   └── irs/                  # User IRs
├── audio/                    # Shootout audio segments
├── videos/                   # Rendered videos
└── source_downloads/
    └── t3k/                  # {model_id}/{url_filename}.nam
```

---

## Task 1: Stop services and migrate data

**Purpose:** Safely copy live data from named volume to bind mount directory, verify counts, clean stale archive files.

**Step 1: Stop worker, scheduler, and all services**

```bash
docker compose --profile jobs stop worker scheduler
docker compose stop webapp nginx astro video
```

**Step 2: Clean stale archive files from `../gts-storage/`**

The old `models/` dir has 4 stale `{tone_id}_{model_id}_{size}.nam` files and a `t3k/` subdir with 74 old files. These use a different naming convention and are superseded by the volume data.

```bash
# Back up first just in case
mkdir -p ../gts-storage/.archive-backup
mv ../gts-storage/models ../gts-storage/.archive-backup/models
mv ../gts-storage/outputs ../gts-storage/.archive-backup/outputs
mv ../gts-storage/segments ../gts-storage/.archive-backup/segments
mv ../gts-storage/uploads ../gts-storage/.archive-backup/uploads
mv ../gts-storage/videos ../gts-storage/.archive-backup/videos
```

**Step 3: Create target directory structure**

```bash
mkdir -p ../gts-storage/{models,uploads/di_tracks,uploads/irs,audio,videos,source_downloads}
```

**Step 4: Copy live data from named volume**

```bash
# Copy models (4,778 files)
docker run --rm -v gts-processed-main:/src -v $(realpath ../gts-storage):/dst alpine \
  cp -a /src/models/. /dst/models/

# Copy source_downloads (10,497 dirs)
docker run --rm -v gts-processed-main:/src -v $(realpath ../gts-storage):/dst alpine \
  cp -a /src/source_downloads/. /dst/source_downloads/

# Copy shootouts (empty but keep structure)
docker run --rm -v gts-processed-main:/src -v $(realpath ../gts-storage):/dst alpine \
  sh -c "[ -d /src/shootouts ] && cp -a /src/shootouts/. /dst/audio/ || true"
```

**Step 5: Verify file counts match**

```bash
# Models count: expect 4,778
docker run --rm -v gts-processed-main:/data alpine sh -c "ls /data/models/*.nam | wc -l"
ls ../gts-storage/models/*.nam | wc -l

# Source downloads count: expect 10,497
docker run --rm -v gts-processed-main:/data alpine sh -c "ls /data/source_downloads/t3k/ | wc -l"
ls ../gts-storage/source_downloads/t3k/ | wc -l
```

**Step 6: Fix ownership**

```bash
# Ensure appuser (UID 1000) owns all files
sudo chown -R 1000:1000 ../gts-storage/
```

**Commit:** No code changes yet, no commit.

---

## Task 2: Add `GTS_STORAGE_ROOT` env var to Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.ci.yml`
- Modify: `.env.example`

**Step 1: Update `docker-compose.yml`**

Replace named volume mounts with bind mount on webapp (line 86), worker (lines 168-170), and video (lines 256-257):

For **webapp** service, replace:
```yaml
      - upload_data:/app/uploads
```
with:
```yaml
      - ../gts-storage:/app/storage
```

Add `GTS_STORAGE_ROOT` to webapp environment (after `ENV` line):
```yaml
      GTS_STORAGE_ROOT: /app/storage
```

For **worker** service, replace:
```yaml
      - upload_data:/app/uploads
      - processed_data:/app/processed
      - processed_data:/processed_data
```
with:
```yaml
      - ../gts-storage:/app/storage
```

Add `GTS_STORAGE_ROOT` to worker environment:
```yaml
      GTS_STORAGE_ROOT: /app/storage
```

For **video** service, replace:
```yaml
      - upload_data:/app/uploads
      - processed_data:/app/processed
```
with:
```yaml
      - ../gts-storage:/app/storage
```

Add `GTS_STORAGE_ROOT` to video environment:
```yaml
      GTS_STORAGE_ROOT: /app/storage
```

Remove the named volume definitions at the bottom (lines 283-286):
```yaml
  upload_data:
    name: gts-uploads-${GTS_WORKTREE:-main}
  processed_data:
    name: gts-processed-${GTS_WORKTREE:-main}
```

**Step 2: Update `docker-compose.ci.yml`**

CI needs an ephemeral storage directory, not the shared bind mount. Add a tmpfs or use a CI-specific temp directory.

Replace the volume definitions (lines 66-67):
```yaml
  upload_data:
  processed_data:
```
with:
```yaml
  # CI uses a temp directory for storage isolation (not shared gts-storage)
```

Add to webapp and worker services in CI override:
```yaml
  webapp:
    ...
    volumes:
      - /tmp/gts-ci-storage-${CI_JOB_ID:-local}:/app/storage
    environment:
      ...
      GTS_STORAGE_ROOT: /app/storage

  worker:
    ...
    volumes:
      - /tmp/gts-ci-storage-${CI_JOB_ID:-local}:/app/storage
    environment:
      ...
      GTS_STORAGE_ROOT: /app/storage
```

**Step 3: Update `.env.example`**

Replace lines 86-96:
```
# Upload storage (DI tracks, user uploads)
UPLOAD_PATH=/app/uploads

# Processed output storage (rendered audio, videos)
PROCESSED_PATH=/app/processed

# NAM models storage
NAM_MODELS_PATH=/app/models/nam

# IR files storage
IR_FILES_PATH=/app/models/ir
```

with:
```
# Unified storage root (bind-mounted from ../gts-storage/)
# All subdirectories derived: models/, uploads/, audio/, videos/, source_downloads/
GTS_STORAGE_ROOT=/app/storage
```

**Step 4: Commit**

```
refactor(infra): replace named volumes with unified storage bind mount
```

---

## Task 3: Update `Dockerfile.worker`

**Files:**
- Modify: `infrastructure/docker/Dockerfile.worker:67`

**Step 1: Replace directory creation**

Replace:
```dockerfile
RUN mkdir -p /app/uploads /app/processed && \
    chown -R gts:gts /app
```

with:
```dockerfile
RUN mkdir -p /app/storage && \
    chown -R gts:gts /app
```

**Step 2: Commit**

```
refactor(infra): update Dockerfile.worker for unified storage path
```

---

## Task 4: Update webapp upload paths (remove hardcoded paths)

**Files:**
- Modify: `apps/webapp/src/webapp/config/uploads.py:34`
- Modify: `apps/webapp/src/webapp/api/v1/di_tracks.py:62`

**Step 1: Update `uploads.py`**

Replace the `get_upload_base()` function body (line 34):
```python
    return Path("/app/uploads")
```

with:
```python
    return Path(os.environ["GTS_STORAGE_ROOT"]) / "uploads"
```

**Step 2: Update `di_tracks.py`**

Replace the hardcoded path (line 61-62):
```python
    # Create upload directory structure: /app/uploads/di-tracks/{user_id}/
    upload_base = Path("/app/uploads/di-tracks")
```

with:
```python
    # Create upload directory structure: {storage}/uploads/di_tracks/{user_id}/
    upload_base = Path(os.environ["GTS_STORAGE_ROOT"]) / "uploads" / "di_tracks"
```

Add `import os` at top if not already present.

Note: the directory name changes from `di-tracks` (hyphen) to `di_tracks` (underscore) to match the architecture spec. This is safe since uploads volume was empty.

**Step 3: Commit**

```
refactor(webapp): derive upload paths from GTS_STORAGE_ROOT
```

---

## Task 5: Update worker storage paths (remove hardcoded paths)

**Files:**
- Modify: `apps/worker/src/worker/jobs/audio.py:33`
- Modify: `apps/worker/src/worker/jobs/master_audio.py:31,89`
- Modify: `apps/worker/src/worker/services/gear_mapper.py:306`
- Modify: `apps/worker/src/worker/jobs/source_sync.py:65`

**Step 1: Update `audio.py` (line 33)**

Replace:
```python
STORAGE_ROOT = Path(os.getenv("WORKER_STORAGE_ROOT", "/app/processed"))
```

with:
```python
STORAGE_ROOT = Path(os.environ["GTS_STORAGE_ROOT"])
```

**Step 2: Update `master_audio.py`**

Line 31 — same replacement as audio.py:
```python
STORAGE_ROOT = Path(os.environ["GTS_STORAGE_ROOT"])
```

Line 85 — replace `STORAGE_ROOT / "shootouts"` with `STORAGE_ROOT / "audio"`:
```python
            output_dir = STORAGE_ROOT / "audio" / str(shootout_id)
```

Line 89 — remove the hardcoded fallback:
```python
            output_dir = f"/app/processed/shootouts/{shootout_id}"
```
This entire `except` block (lines 87-89) should be removed. If `mkdir` fails, it should fail loudly.

**Step 3: Update `gear_mapper.py` (line 306)**

Replace:
```python
        storage_root = Path(os.getenv("WORKER_STORAGE_ROOT", "/app/processed"))
```

with:
```python
        storage_root = Path(os.environ["GTS_STORAGE_ROOT"])
```

**Step 4: Update `source_sync.py` (line 65)**

Replace:
```python
    base_path = Path(os.getenv("T3K_SOURCE_DOWNLOADS_PATH", "/app/processed/source_downloads/t3k"))
```

with:
```python
    base_path = Path(os.environ["GTS_STORAGE_ROOT"]) / "source_downloads" / "t3k"
```

**Step 5: Commit**

```
refactor(worker): derive all storage paths from GTS_STORAGE_ROOT
```

---

## Task 6: Update source adapter (T3K model downloader)

**Files:**
- Modify: `sources/t3k/src/source_t3k/services/model_downloader.py` — no hardcoded paths here (receives `base_path` via constructor), but verify the caller in `source_sync.py` (already updated in Task 5)

No code changes needed in model_downloader.py itself — it receives `base_path` from `source_sync.py._build_model_downloader()` which was updated in Task 5.

**Verify:** The downloader's `_get_model_path` (line 39-45) builds `base_path / str(model.id) / filename` — this produces `{GTS_STORAGE_ROOT}/source_downloads/t3k/{model_id}/{filename}.nam`. The existing files on disk match this layout, so downloads will be skipped for existing files (line 59: `if path.exists(): return None`).

**Step 1: Commit** (skip if no changes)

---

## Task 7: Update `sync_from_archive.py`

**Files:**
- Modify: `scripts/sync_from_archive.py:277,289,310`

**Step 1: Update container paths**

The script runs commands inside the worker container. Replace all `/app/processed` references with `/app/storage`.

Line 277: Replace `"/app/processed/source_downloads/t3k"` with `"/app/storage/source_downloads/t3k"`

Line 289: Replace `"/app/processed/source_downloads/t3k/"` with `"/app/storage/source_downloads/t3k/"`

Line 310: Replace `"/app/processed/source_downloads/t3k/"` with `"/app/storage/source_downloads/t3k/"`

**Step 2: Commit**

```
refactor(scripts): update sync_from_archive for unified storage path
```

---

## Task 8: Update `seed_di_tracks.py`

**Files:**
- Modify: `scripts/seed_di_tracks.py:82,247`

**Step 1: Update default path (line 82)**

Replace:
```python
        self.storage_path = storage_path or Path("/app/uploads/di-tracks/")
```

with:
```python
        self.storage_path = storage_path or Path(os.environ["GTS_STORAGE_ROOT"]) / "uploads" / "di_tracks"
```

Add `import os` at top if not already present.

**Step 2: Update CLI help text (line 247)**

Update the help string from `/app/uploads/di-tracks/` to reference `$GTS_STORAGE_ROOT/uploads/di_tracks/`.

**Step 3: Commit**

```
refactor(scripts): update seed_di_tracks for unified storage path
```

---

## Task 9: Update worktree system — remove `volume_uploads`

**Files:**
- Modify: `worktree/config.py:36` — remove `uploads` field from `VolumeConfig`
- Modify: `worktree/registry.py:179,286,408,426,718` — remove `volume_uploads` from schema and queries
- Modify: `worktree/templates.py:196,258,282,320` — replace named volume with bind mount
- Modify: `worktree/templates/docker-compose.override.yml.j2:31,54,78,106` — replace named volume with bind mount
- Modify: `worktree/resources.py:44,74,112,201` — remove uploads volume references
- Modify: `worktree/commands/info.py:137` — remove uploads volume display

**Step 1: Update `config.py`**

Remove `uploads: str` from `VolumeConfig` (line 36).

**Step 2: Update `registry.py`**

- Line 179: Remove `volume_uploads TEXT NOT NULL,` from schema
- Line 286: Remove `volume_uploads = 'gts-uploads-' ...` from migration
- Lines 408,426: Remove `volume_uploads` from INSERT and column list
- Line 718: Remove `uploads=row["volume_uploads"],` from worktree construction

Note: Schema change requires a migration. Add a migration SQL that drops the column:
```sql
ALTER TABLE worktrees DROP COLUMN IF EXISTS volume_uploads;
```
Or handle via the existing migration pattern in `_migrate_v*` functions.

**Step 3: Update `templates.py`**

Line 196: Remove `UPLOADS_VOLUME={worktree.volumes.uploads}`

Lines 258, 282: Replace `{volumes.uploads}:/app/uploads` with `../gts-storage:/app/storage`

Line 320: Remove `{volumes.uploads}:` from volumes section

Add `GTS_STORAGE_ROOT: /app/storage` to environment for webapp and worker services.

**Step 4: Update `templates/docker-compose.override.yml.j2`**

Lines 31, 54, 78: Replace `{{ worktree.volumes.uploads }}:/app/uploads` with `../gts-storage:/app/storage`

Line 106: Remove `{{ worktree.volumes.uploads }}:` from volumes section

Add `GTS_STORAGE_ROOT: /app/storage` to webapp, worker, and video environment sections.

**Step 5: Update `resources.py`**

Line 44: Remove `UPLOADS_VOLUME={worktree.volumes.uploads}`
Line 74: Remove `f"{volumes.uploads}:/data/uploads",`
Line 112: Remove `volumes.uploads: None,`
Line 201: Remove `uploads:{volumes.uploads}` from display string

**Step 6: Update `commands/info.py`**

Line 137: Remove `Uploads:     {worktree.volumes.uploads}` line, replace with:
```
  Storage:     ../gts-storage/ (bind mount)
```

**Step 7: Commit**

```
refactor(worktree): remove volume_uploads, use shared bind mount
```

---

## Task 10: Update tests

**Files:**
- Modify: `tests/integration/webapp/test_di_track_upload.py:193,224-225`
- Modify: `tests/integration/webapp/test_library_tracks_tuning_t130.py:47,99,110`
- Modify: `tests/integration/webapp/test_library_di_tracks_page_t130.py:46,143,169,209,220,301`
- Modify: `tests/integration/webapp/test_di_track_browse_t125.py:48,72`
- Modify: `tests/integration/webapp/test_di_track_browse_page_t125.py:74,98`
- Modify: `tests/unit/worker/test_audio_job.py:293-296`
- Modify: `tests/unit/worker/test_gear_mapper_service.py:375,418,462,504`
- Modify: `tests/unit/worktree/test_video_docker_checks_t80.py:195,245`
- Modify: `tests/unit/worktree/test_video_service_integration_t80.py:92,136,184,228,273`

**Step 1: Update DI track upload test paths**

In all integration test files, replace `/app/uploads/di-tracks/` with `/app/storage/uploads/di_tracks/` in both assertions and fixture data.

For `test_di_track_upload.py`:
- Line 225: `assert file_path.startswith("/app/storage/uploads/di_tracks/")`

For `test_library_*` and `test_di_track_browse_*` files: update all `file_path="/app/uploads/di-tracks/..."` fixture strings to `file_path="/app/storage/uploads/di_tracks/..."`.

**Step 2: Update worker test env vars**

In `test_gear_mapper_service.py`, replace:
```python
monkeypatch.setenv("WORKER_STORAGE_ROOT", str(tmp_path))
```
with:
```python
monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
```

In `test_audio_job.py`, update test name and docstring to reference `storage` instead of `processed_data volume`. Ensure `GTS_STORAGE_ROOT` is set in test env.

**Step 3: Update worktree test fixtures**

In `test_video_docker_checks_t80.py` and `test_video_service_integration_t80.py`, remove all `uploads="gts-uploads-*"` references from `VolumeConfig` construction. These tests create `VolumeConfig` objects — update to match the new schema without `uploads`.

**Step 4: Run tests**

```bash
just tdd tests/unit/worker/
just tdd tests/unit/worktree/
just tdd tests/integration/webapp/
```

**Step 5: Commit**

```
test: update storage path references for unified bind mount
```

---

## Task 11: Update documentation and skills

**Files:**
- Modify: `DEVELOPMENT.md:226`
- Modify: `../wiki/GTS-Technical-Architecture.md` (lines 968-980, 1817)
- Modify: `.claude/skills/gts-video/SKILL.md:238-239,415`
- Modify: `.claude/skills/gts-architecture/references/web-application.md:195,200`
- Modify: `.claude/skills/gts-architecture/references/infrastructure.md:97`
- Modify: `.claude/skills/incident-response/SKILL.md:379`

**Step 1: Update wiki**

In `GTS-Technical-Architecture.md`, update the File Storage section (lines 968-980):
```markdown
## File Storage

Shared bind mount (`../gts-storage/`) — all worktrees share one storage directory.

### Storage Layout

```
/app/storage/
├── models/              # Core gear models ({uuid}.nam)
├── uploads/
│   ├── di_tracks/       # User-uploaded guitar recordings
│   └── irs/             # User-uploaded impulse responses
├── audio/               # Processed shootout audio segments
├── videos/              # Generated shootout comparison videos
└── source_downloads/    # Raw source adapter downloads
    └── t3k/             # T3K models ({model_id}/{filename}.nam)
```
```

Line 1817: Already says `../gts-storage/` — keep as-is.

**Step 2: Update DEVELOPMENT.md**

Line 226 already says `../gts-storage/` — verify it's accurate, update description if needed.

**Step 3: Update skills**

In `gts-video/SKILL.md`, replace:
```yaml
      - upload_data:/app/uploads
      - processed_data:/app/processed
```
with:
```yaml
      - ../gts-storage:/app/storage
```

Update FFmpeg log path reference (line 415): `/app/processed/{job_id}/` → `/app/storage/audio/{job_id}/`

In `gts-architecture/references/web-application.md`:
- Line 195: Replace "Docker volume (`gts-storage`)" with "Shared bind mount (`../gts-storage/`)"
- Line 200: Update the `/app/storage/` tree to match new layout

In `gts-architecture/references/infrastructure.md`:
- Line 97: Already says `../gts-storage/` — verify accuracy

In `incident-response/SKILL.md`:
- Line 379: Replace `/app/storage/` command if it references old paths

**Step 4: Commit**

```
docs: update storage references for unified bind mount
```

---

## Task 12: Restart services and verify

**Step 1: Regenerate worktree config**

```bash
./worktree.py setup main
```

This regenerates `docker-compose.override.yml` and `.env.local` with the new template (no uploads volume).

**Step 2: Start services**

```bash
just up-d
```

**Step 3: Verify storage is mounted correctly**

```bash
docker compose exec webapp ls -la /app/storage/
docker compose exec worker ls -la /app/storage/
docker compose exec worker ls /app/storage/models/ | wc -l   # expect 4,778
docker compose exec worker ls /app/storage/source_downloads/t3k/ | wc -l  # expect 10,497
```

**Step 4: Verify worker can read model files**

```bash
# Pick a known core UUID model and verify it's readable
docker compose exec worker python -c "
import os
from pathlib import Path
root = Path(os.environ['GTS_STORAGE_ROOT'])
models = list((root / 'models').glob('*.nam'))
print(f'Models found: {len(models)}')
print(f'First: {models[0].name}, size: {models[0].stat().st_size}')
"
```

**Step 5: Verify downloads skip existing files**

The T3K sync, when triggered, should skip downloading models that already exist at `{GTS_STORAGE_ROOT}/source_downloads/t3k/{model_id}/{filename}.nam`. This is handled by `ModelDownloader._get_model_path()` + the `path.exists()` check on line 59 of `model_downloader.py`.

**Step 6: Run quality gates**

```bash
just check
```

**Step 7: Commit any remaining fixes, then final commit**

```
feat(infra): unified storage bind mount at ../gts-storage

Replace per-worktree Docker named volumes (upload_data, processed_data)
with a single shared bind mount (../gts-storage:/app/storage).

All storage paths derived from GTS_STORAGE_ROOT env var — no hardcoded
paths in application code. Storage is shared across worktrees.

Layout: models/, uploads/, audio/, videos/, source_downloads/
```

---

## Task 13: Clean up old named volumes (manual, after verification)

**Only after everything is confirmed working:**

```bash
docker volume rm gts-uploads-main gts-processed-main
# Also clean up stale worktree volumes if any:
docker volume rm 47-epic-phase-3b-audio-processing-library_gts-uploads-47-epic-phase-3b-audio-processing-library 2>/dev/null
docker volume rm 86-epic-phase-4-remainder-di-tracks-chain-g_gts-uploads-86-epic-phase-4-remainder-di-tracks-chain-g 2>/dev/null
docker volume rm codex_gts-uploads-codex 2>/dev/null
```

And remove the backup:
```bash
rm -rf ../gts-storage/.archive-backup/
```

---

## Summary of env var changes

| Old env var | New env var | Notes |
|---|---|---|
| `WORKER_STORAGE_ROOT` | `GTS_STORAGE_ROOT` | Used by worker, webapp, video |
| `T3K_SOURCE_DOWNLOADS_PATH` | (removed) | Derived: `$GTS_STORAGE_ROOT/source_downloads/t3k` |
| `UPLOAD_PATH` | (removed) | Derived: `$GTS_STORAGE_ROOT/uploads` |
| `PROCESSED_PATH` | (removed) | Derived: `$GTS_STORAGE_ROOT` |
| `NAM_MODELS_PATH` | (removed) | Derived: `$GTS_STORAGE_ROOT/models` |
| `IR_FILES_PATH` | (removed) | Derived: `$GTS_STORAGE_ROOT/uploads/irs` |

## Key invariant

`GTS_STORAGE_ROOT` has **no default**. If unset, `os.environ["GTS_STORAGE_ROOT"]` raises `KeyError` immediately. This prevents silent use of wrong paths. Set in docker-compose.yml `environment:` for every service that touches files.
