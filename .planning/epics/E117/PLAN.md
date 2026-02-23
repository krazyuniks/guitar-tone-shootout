# Plan: Epic #117

## Goal

Rename libs/ to model/ and create infra/messaging/ to establish the canonical project layout that all subsequent migration epics build upon, with zero functional changes.

## Observable Truths

1. A developer browsing the project root sees model/gts/, model/audio/, and model/video/ directories containing domain code, and the libs/ directory no longer exists.
2. A developer browsing infra/messaging/ sees the messaging infrastructure modules: pgmq_client.py, consumer_base.py, message_bus.py, envelope.py, commands.py, and events.py.
3. A developer reading any Python file in the project sees imports using 'from gts.' for domain code and 'from messaging.' for messaging infrastructure — no references to the old 'from core.' import paths remain.
4. A developer running 'just up-d' sees all Docker containers (webapp, db, nginx, t3k-sync, audio-worker, video-worker) build and start successfully with healthy status.
5. A developer running 'just check' sees all quality gates pass: ruff lint, mypy type checking, import-linter BC contracts, and the full test suite.

## User Journeys

### Journey J1: Developer verifying project structure after rename

A developer opens the project root and sees model/ and infra/ directories instead of libs/. They browse model/gts/src/gts/ to confirm domain entities, ports, records, and services are present. They browse infra/messaging/src/messaging/ to confirm pgmq_client, consumer_base, commands, events, envelope, and message_bus modules. They open a Python file such as apps/webapp/src/webapp/services/signal_chain_service.py and see 'from gts.domain.entities' rather than the old 'from core.domain.entities'. They verify no 'from core.' imports remain anywhere with a project-wide search.

**Truths covered:** 1, 2, 3
**Entry point:** /
**Critical transitions:**
- project root -> model/gts/src/gts/domain/entities/ (file browser navigation)
- project root -> infra/messaging/src/messaging/ (file browser navigation)
- infra/messaging/src/messaging/ -> apps/webapp/src/webapp/services/ (grep for import statements)

### Journey J2: Developer verifying application functionality is preserved

A developer runs 'just up-d' and all containers start with healthy status. They run 'just check' which executes ruff lint, mypy type checking, import-linter BC boundary contracts, and the full test suite — all pass green. They verify the webapp responds at localhost:9000 with a health check. The T3K sync, audio-worker, and video-worker containers all show healthy in 'just status'.

**Truths covered:** 3, 4, 5
**Entry point:** terminal
**Critical transitions:**
- terminal -> Docker containers running (just up-d && just status)
- Docker containers running -> quality gates pass (just check)
- quality gates pass -> webapp health verified (just health)

## Stories

### Story: Directory rename and package configuration (`01-directory-restructure`)

**Purpose:** Rename libs/ to model/, rename the core package to gts, create infra/messaging/ with moved messaging modules, and update all pyproject.toml files and lockfile to reflect the new structure.

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []
- max_turns: 40

**Scope:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `libs/core/pyproject.toml`
- Modify: `libs/audio/pyproject.toml`
- Modify: `libs/video/pyproject.toml`
- Modify: `apps/webapp/pyproject.toml`
- Modify: `apps/worker/pyproject.toml`
- Modify: `apps/t3k_sync/pyproject.toml`
- Modify: `apps/audio_worker/pyproject.toml`
- Modify: `apps/video_worker/pyproject.toml`
- Modify: `sources/t3k/pyproject.toml`
- Modify: `src/gts/__init__.py`

**Wiki Sections:** GTS-Technical-Architecture :: architecture-layers, GTS-Technical-Architecture :: design-patterns

**Implementation Notes:**
- Create model/ directory and rename libs packages: `mkdir model && git mv libs/core model/gts && git mv model/gts/src/core model/gts/src/gts && git mv libs/audio model/audio && git mv libs/video model/video && rmdir libs`
- Create infra/messaging/ package structure: `mkdir -p infra/messaging/src/messaging`
- Move messaging files from model/gts/ to infra/messaging/src/messaging/ using git mv: pgmq_client.py and consumer_base.py (from src/gts/services/), envelope.py, commands.py, events.py (from src/gts/records/), message_bus.py (from src/gts/ports/)
- Create infra/messaging/pyproject.toml: name='gts-messaging', packages=['src/messaging'], dependencies on pydantic>=2.10.0 and sqlalchemy[asyncio]>=2.0.36 only
- Create infra/messaging/src/messaging/__init__.py with appropriate exports
- Create infra/messaging/README.md (required by Dockerfile COPY patterns)
- Update model/gts/pyproject.toml: name='gts-domain', packages=['src/gts']
- Update model/gts/src/gts/__init__.py, records/__init__.py, services/__init__.py, ports/__init__.py to remove re-exports of moved messaging modules
- Update root pyproject.toml: workspace members from 'libs/*' to 'model/*' and 'infra/*'; import-linter root_packages replace 'core' with 'gts' and add 'messaging'; all import-linter contracts replace 'core' with 'gts' and add messaging contracts; ruff known-first-party replace 'core' with 'gts' and add 'messaging'; coverage source from 'libs' to 'model' and add 'infra'; remove hatch build target for src/gts
- Update all downstream pyproject.toml dependencies: 'gts-core' → 'gts-domain' everywhere; add 'gts-messaging' dependency to apps/worker, apps/t3k_sync, apps/audio_worker, apps/video_worker
- Update model/audio/pyproject.toml and model/video/pyproject.toml: dependency from gts-core to gts-domain
- Delete src/gts/__init__.py (the root virtual package — gts namespace now belongs to model/gts)
- Regenerate the lockfile after all pyproject.toml changes: run `uv lock` to sync uv.lock with the new workspace members and dependency names
- IMPORTANT: gear_sync.py MUST remain in model/gts/src/gts/records/ — it is domain, not messaging. Only move the 6 messaging modules (pgmq_client.py, consumer_base.py, envelope.py, commands.py, events.py, message_bus.py).

**Truths Addressed:** 1, 2

---

### Validation Checkpoint: After Directory rename and package configuration

**Type:** process
**Checks:**
- model/gts/, model/audio/, model/video/ directories exist with correct package structure and libs/ directory is gone (evidence: command, exit_code, output_tail) [cmd: `test -d model/gts/src/gts/domain && test -d model/audio/src/audio && test -d model/video/src/video && test -d infra/messaging/src/messaging && ! test -d libs`]
- Domain entities directory is navigable from project root and contains Python source files (evidence: command, exit_code, output_tail) [cmd: `ls model/gts/src/gts/domain/entities/*.py | head -5 && echo 'OK: domain entities visible'`]
- Messaging modules directory is navigable from project root and contains all six expected modules (evidence: command, exit_code, output_tail) [cmd: `ls infra/messaging/src/messaging/pgmq_client.py infra/messaging/src/messaging/consumer_base.py infra/messaging/src/messaging/message_bus.py infra/messaging/src/messaging/envelope.py infra/messaging/src/messaging/commands.py infra/messaging/src/messaging/events.py && echo 'OK: all 6 messaging modules visible'`]
- Old messaging files are removed from model/gts/ — confirms git mv (not copy) (evidence: command, exit_code, output_tail) [cmd: `! test -f model/gts/src/gts/services/pgmq_client.py && ! test -f model/gts/src/gts/services/consumer_base.py && ! test -f model/gts/src/gts/records/envelope.py && ! test -f model/gts/src/gts/records/commands.py && ! test -f model/gts/src/gts/records/events.py && ! test -f model/gts/src/gts/ports/message_bus.py && echo 'OK: old messaging files removed from model/gts/'`]
- gear_sync.py remains in model/gts/src/gts/records/ (domain record, not messaging) (evidence: command, exit_code, output_tail) [cmd: `test -f model/gts/src/gts/records/gear_sync.py && echo 'OK: gear_sync.py preserved in domain records'`]
- signal_chain_validator.py and permutation_calculator.py remain in model/gts/ domain services (evidence: command, exit_code, output_tail) [cmd: `test -f model/gts/src/gts/services/signal_chain_validator.py && test -f model/gts/src/gts/services/permutation_calculator.py && echo 'OK: domain services preserved'`]
- All pyproject.toml files have valid TOML syntax and correct package names (gts-domain, gts-audio, gts-video, gts-messaging) (evidence: command, exit_code, output_tail) [cmd: `python3 -c "import tomllib; gts=tomllib.load(open('model/gts/pyproject.toml','rb')); assert gts['project']['name']=='gts-domain', f'expected gts-domain, got {gts[\"project\"][\"name\"]}'; aud=tomllib.load(open('model/audio/pyproject.toml','rb')); assert aud['project']['name']=='gts-audio', f'expected gts-audio, got {aud[\"project\"][\"name\"]}'; vid=tomllib.load(open('model/video/pyproject.toml','rb')); assert vid['project']['name']=='gts-video', f'expected gts-video, got {vid[\"project\"][\"name\"]}'; msg=tomllib.load(open('infra/messaging/pyproject.toml','rb')); assert msg['project']['name']=='gts-messaging', f'expected gts-messaging, got {msg[\"project\"][\"name\"]}'; print('OK: all package names correct')"`]
- Root pyproject.toml has updated workspace members (model/*, infra/*), ruff known-first-party (gts, messaging), import-linter root_packages (gts, messaging), and coverage source (model, infra) — no stale libs/core references remain (evidence: command, exit_code, output_tail) [cmd: `python3 -c "import tomllib; cfg=tomllib.load(open('pyproject.toml','rb')); members=cfg['tool']['uv']['workspace']['members']; assert 'model/*' in members, f'model/* missing from workspace: {members}'; assert 'infra/*' in members, f'infra/* missing from workspace: {members}'; assert 'libs/*' not in members, f'libs/* still in workspace: {members}'; roots=cfg['tool']['importlinter']['root_packages']; assert 'gts' in roots, f'gts missing from import-linter roots: {roots}'; assert 'messaging' in roots, f'messaging missing from import-linter roots: {roots}'; assert 'core' not in roots, f'core still in import-linter roots: {roots}'; fp=cfg['tool']['ruff']['lint']['isort']['known-first-party']; assert 'gts' in fp, f'gts missing from ruff first-party: {fp}'; assert 'messaging' in fp, f'messaging missing from ruff first-party: {fp}'; assert 'core' not in fp, f'core still in ruff first-party: {fp}'; cov=cfg['tool']['coverage']['run']['source']; assert 'model' in cov, f'model missing from coverage source: {cov}'; assert 'infra' in cov, f'infra missing from coverage source: {cov}'; assert 'libs' not in cov, f'libs still in coverage source: {cov}'; print('OK: root pyproject.toml fully updated')"`]
- uv.lock is regenerated and consistent with updated pyproject.toml workspace members (evidence: command, exit_code, output_tail) [cmd: `uv lock --check`]

---

### Story: Docker and build system updates (`02-infrastructure`)

**Purpose:** Update all Dockerfiles, docker-compose files, justfile, and worktree template to reference the new model/ and infra/ directory paths instead of libs/.

**Agent:**
- model: codex
- skills: [gts-architecture]
- tools: []
- max_turns: 30

**Scope:**
- Modify: `infrastructure/docker/Dockerfile.dev`
- Modify: `infrastructure/docker/Dockerfile.backend`
- Modify: `infrastructure/docker/Dockerfile.worker`
- Modify: `infrastructure/docker/Dockerfile.t3k-sync`
- Modify: `infrastructure/docker/Dockerfile.audio-worker`
- Modify: `infrastructure/docker/Dockerfile.video`
- Modify: `infrastructure/docker/Dockerfile.scheduler`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.override.yml`
- Modify: `justfile`
- Modify: `worktree/templates/docker-compose.override.yml.j2`

**Wiki Sections:** GTS-Technical-Architecture :: infrastructure

**Implementation Notes:**
- All 7 Dockerfiles reference libs/core/, libs/audio/, libs/video/ in COPY and mkdir commands. Update: libs/core/ → model/gts/, libs/audio/ → model/audio/, libs/video/ → model/video/. Add COPY and mkdir entries for infra/messaging/.
- In Dockerfiles, the mkdir line creates placeholder __init__.py files. Update: libs/core/src/core → model/gts/src/gts, libs/audio/src/audio → model/audio/src/audio, libs/video/src/video → model/video/src/video. Add infra/messaging/src/messaging. Remove src/gts directory creation and COPY.
- docker-compose.yml: update webapp volumes from ./libs:/app/libs to ./model:/app/model and add ./infra:/app/infra. Same for worker, t3k-sync, audio-worker services. Video-worker: ./libs/core:/app/libs/core:ro → ./model/gts:/app/model/gts:ro and ./libs/video:/app/libs/video → ./model/video:/app/model/video. Remove ./src:/app/src mount.
- docker-compose.override.yml: same volume mount updates as base compose file for all services
- justfile: update check-types mypy path from libs/core/ to model/gts/; update check-lint and lint ruff paths from libs/ to model/ and add infra/; update video-studio and video-types cd path from libs/video to model/video
- worktree/templates/docker-compose.override.yml.j2: update all ./libs volume mounts to ./model, add ./infra mounts, update video-worker specific mounts from ./libs/core and ./libs/video to ./model/gts and ./model/video

**Truths Addressed:** 4

---

### Validation Checkpoint: After Docker and build system updates

**Type:** process
**Checks:**
- Dockerfiles no longer reference libs/ paths and DO contain model/gts/, model/audio/, model/video/, and infra/messaging/ COPY paths (evidence: command, exit_code, output_tail) [cmd: `! grep -r 'libs/' infrastructure/docker/Dockerfile.* && grep -q 'model/gts/' infrastructure/docker/Dockerfile.dev && grep -q 'model/audio/' infrastructure/docker/Dockerfile.dev && grep -q 'model/video/' infrastructure/docker/Dockerfile.dev && grep -q 'infra/messaging/' infrastructure/docker/Dockerfile.dev && echo 'OK: Dockerfiles reference model/ and infra/ paths'`]
- docker-compose.yml no longer references ./libs mounts and DOES contain ./model and ./infra volume mounts (evidence: command, exit_code, output_tail) [cmd: `! grep './libs' docker-compose.yml && grep -q './model' docker-compose.yml && grep -q './infra' docker-compose.yml && echo 'OK: compose volumes reference model/ and infra/'`]
- justfile no longer references libs/ paths and DOES contain model/ paths (evidence: command, exit_code, output_tail) [cmd: `! grep 'libs/' justfile && grep -q 'model/' justfile && echo 'OK: justfile references model/ paths'`]
- All Docker containers build successfully, start, and are running (no exited or unhealthy containers) (evidence: command, exit_code, output_tail) [cmd: `just rebuild && just up-d && sleep 15 && docker compose ps --format '{{.Service}}: {{.Status}}' && (docker compose ps | grep -qiE 'exit|unhealthy' && echo 'FAIL: exited or unhealthy containers detected' && exit 1 || echo 'OK: all containers running')`]
- Webapp responds to health check at localhost:9000 (evidence: command, exit_code, output_tail) [cmd: `just health | grep -q 'webapp' && echo 'OK: webapp listed in healthy services'`]

---

### Story: Python import updates and quality verification (`03-import-migration`)

**Purpose:** Update all Python import statements from core.* to gts.* (for domain) and messaging.* (for messaging infrastructure) across the entire codebase, then verify all quality gates pass.

**Agent:**
- model: codex
- skills: [gts-architecture, gts-backend-dev, gts-testing]
- tools: []
- max_turns: 50

**Scope:**
- Modify: `apps/webapp/src/webapp/adapters/persistence/models/base.py`
- Modify: `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py`
- Modify: `apps/webapp/src/webapp/services/signal_chain_service.py`
- Modify: `apps/webapp/src/webapp/api/v1/html.py`
- Modify: `apps/webapp/src/webapp/api/v1/schemas/gear.py`
- Modify: `apps/webapp/src/webapp/services/job_service.py`
- Modify: `apps/worker/src/worker/services/gear_mapper.py`
- Modify: `apps/worker/src/worker/jobs/audio.py`
- Modify: `apps/t3k_sync/src/t3k_sync/consumer.py`
- Modify: `apps/t3k_sync/src/t3k_sync/source_sync.py`
- Modify: `apps/audio_worker/src/audio_worker/consumer.py`
- Modify: `apps/video_worker/src/video_worker/consumer.py`
- Modify: `sources/t3k/src/source_t3k/adapters/outbound/publisher.py`
- Modify: `tests/regression/test_stack.py`
- Modify: `tests/unit/core/test_messaging.py`
- Modify: `tests/integration/webapp/test_repositories.py`
- Modify: `tests/integration/audio/test_chain_execution.py`

**Wiki Sections:** GTS-Technical-Architecture :: architecture-layers, GTS-Technical-Architecture :: domain-model, GTS-Technical-Architecture :: design-patterns, GTS-Technical-Architecture :: data-ingestion

**Implementation Notes:**
- This story updates 176+ Python files. Use systematic batch replacement for efficiency.
- MESSAGING IMPORTS (do first — these are specific mappings): 'from core.records.envelope' → 'from messaging.envelope'; 'from core.records.commands' → 'from messaging.commands'; 'from core.records.events' → 'from messaging.events'; 'from core.ports.message_bus' → 'from messaging.message_bus'; 'from core.services.pgmq_client' → 'from messaging.pgmq_client'; 'from core.services.consumer_base' → 'from messaging.consumer_base'
- DOMAIN IMPORTS (do second — broad replacement): 'from core.' → 'from gts.' for all remaining references. This covers core.domain.entities, core.domain.value_objects, core.domain.auth_gate, core.ports.repositories, core.ports.audio_processor, core.ports.video_renderer, core.ports.video_render_client, core.services.signal_chain_validator, core.services.permutation_calculator, core.records.gear_sync
- Also update 'import core' → 'import gts' if any bare imports exist
- Update files in ALL directories: apps/ (43 files), sources/ (2 files), tests/ (97 files), AND files within model/gts/, model/audio/, model/video/, infra/messaging/ that have internal cross-references
- Key internal files: model/gts/src/gts/domain/entities/__init__.py (re-exports), model/gts/src/gts/domain/value_objects/__init__.py (re-exports), model/gts/src/gts/ports/__init__.py, model/gts/src/gts/records/__init__.py, model/gts/src/gts/services/__init__.py, model/audio/src/audio/processing/*.py, model/video/src/video/*.py, infra/messaging/src/messaging/*.py
- Update import-linter contract references in test assertions if any tests validate import paths
- After all replacements, run 'just rebuild' to rebuild containers with new paths, then 'just check' to verify lint, types, imports, and tests all pass. Fix any remaining issues.
- Verify no 'from core.' imports remain: grep -r 'from core\.' apps/ sources/ tests/ model/ infra/ should return zero results

**Truths Addressed:** 3, 5

---

### Validation Checkpoint: After Python import updates and quality verification

**Type:** quality
**Checks:**
- No 'from core.' imports remain in the Python codebase (evidence: command, exit_code, output_tail) [cmd: `! grep -r 'from core\.' apps/ sources/ tests/ model/ infra/ --include='*.py'`]
- No messaging types imported via gts.* re-export paths — all messaging imports use 'from messaging.' directly (evidence: command, exit_code, output_tail) [cmd: `! grep -rE 'from gts\.(records\.(envelope|commands|events)|ports\.message_bus|services\.(pgmq_client|consumer_base))' apps/ sources/ tests/ model/ infra/ --include='*.py'`]
- Each consumer app (t3k_sync, audio_worker, video_worker) imports from 'messaging.*' namespace, confirming messaging extraction works end-to-end (evidence: command, exit_code, output_tail) [cmd: `grep -rq 'from messaging\.' apps/t3k_sync/ --include='*.py' && grep -rq 'from messaging\.' apps/audio_worker/ --include='*.py' && grep -rq 'from messaging\.' apps/video_worker/ --include='*.py' && echo 'OK: all consumer apps use messaging imports'`]
- signal_chain_validator.py and permutation_calculator.py remain in model/gts/ domain services after import migration (evidence: command, exit_code, output_tail) [cmd: `test -f model/gts/src/gts/services/signal_chain_validator.py && test -f model/gts/src/gts/services/permutation_calculator.py && echo 'OK: domain services preserved'`]
- T3K sync consumer can import all messaging dependencies and process startup succeeds (evidence: command, exit_code, output_tail) [cmd: `docker compose exec -T t3k-sync python -c "from t3k_sync.consumer import T3KConsumer; from messaging.pgmq_client import PgmqClient; from messaging.consumer_base import BaseConsumer; from messaging.envelope import MessageEnvelope; from messaging.commands import SyncGearCommand; from gts.domain.entities import Gear; print('OK: T3K sync imports verified')" && just tdd tests/unit/t3k/ -v`]
- Full quality gate passes: ruff lint, mypy type checking, import-linter BC contracts, and full test suite (evidence: command, exit_code, output_tail) [cmd: `just check`]
- All Docker containers build, start, and remain running after import migration (no exited or unhealthy containers) (evidence: command, exit_code, output_tail) [cmd: `just rebuild && just up-d && sleep 15 && docker compose ps --format '{{.Service}}: {{.Status}}' && (docker compose ps | grep -qiE 'exit|unhealthy' && echo 'FAIL: exited or unhealthy containers detected' && exit 1 || echo 'OK: all containers running')`]
- Webapp responds to health check at localhost:9000 after full migration (evidence: command, exit_code, output_tail) [cmd: `docker compose exec -T webapp python -c "import urllib.request; r = urllib.request.urlopen('http://localhost:8000/health'); assert r.status == 200; print('OK: webapp health check passed')"`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. A developer browsing the project root sees model/gts/, model/audio/, and model/video/ directories containing domain code, and the libs/ directory no longer exists. | `pyproject.toml`, `uv.lock`, `libs/core/pyproject.toml` (+9 more) | Directory rename and package configuration |
| 2. A developer browsing infra/messaging/ sees the messaging infrastructure modules: pgmq_client.py, consumer_base.py, message_bus.py, envelope.py, commands.py, and events.py. | `pyproject.toml`, `uv.lock`, `libs/core/pyproject.toml` (+9 more) | Directory rename and package configuration |
| 3. A developer reading any Python file in the project sees imports using 'from gts.' for domain code and 'from messaging.' for messaging infrastructure — no references to the old 'from core.' import paths remain. | `apps/webapp/src/webapp/adapters/persistence/models/base.py`, `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py`, `apps/webapp/src/webapp/services/signal_chain_service.py` (+14 more) | Python import updates and quality verification |
| 4. A developer running 'just up-d' sees all Docker containers (webapp, db, nginx, t3k-sync, audio-worker, video-worker) build and start successfully with healthy status. | `infrastructure/docker/Dockerfile.dev`, `infrastructure/docker/Dockerfile.backend`, `infrastructure/docker/Dockerfile.worker` (+8 more) | Docker and build system updates |
| 5. A developer running 'just check' sees all quality gates pass: ruff lint, mypy type checking, import-linter BC contracts, and the full test suite. | `apps/webapp/src/webapp/adapters/persistence/models/base.py`, `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py`, `apps/webapp/src/webapp/services/signal_chain_service.py` (+14 more) | Python import updates and quality verification |
