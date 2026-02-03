# Implementation Plan: AGENTS.md Update + Phases 1-2

## Overview

Three sequential tasks:
1. **Pre-Task**: Update AGENTS.md for new architecture
2. **Phase 1**: Infrastructure Foundation (uv workspaces, Docker, databases)
3. **Phase 2**: Core Domain Library (libs/core/)

---

## Code Decision Criteria

When evaluating archive code, apply these criteria (not just architecture spec):

| Verdict | Criteria |
|---------|----------|
| **REFACTOR** | Clean DDD patterns, modern Python (3.12+, type hints), immutable value objects, no framework leakage |
| **PARTIAL** | Good logic but needs: T3K-specific removal, path updates, Protocol conversion, aggregate boundary fixes |
| **DISCARD** | Tight coupling, mutable state, framework leakage, no tests, anti-patterns |

**Archive path**: `/home/ryan/Work/guitar-tone-worktrees-archive-20260202/main/`

---

## Pre-Task: Update AGENTS.md

**Goal**: Update AGENTS.md to reflect new architecture while keeping the same format/style.

### Sections to Update

| Section | Changes |
|---------|---------|
| **Quick Start** | Update worktree.py setup, keep port pattern |
| **How to Run Commands** | Add `uv sync`, update just commands |
| **Stack** | Add: uv workspaces, dual databases, pgmq, import-linter |
| **Infrastructure Architecture** | Dual DB (gts_core + gts_t3k_source), worker bridges databases |
| **Project Structure** | Complete rewrite to new layout |
| **Key Patterns** | Add dependency rules table, update backend patterns |
| **Rules** | Update for uv workspace, dual-database awareness |

### New Project Structure

```
gts/
├── pyproject.toml              # Workspace root (uv workspaces)
├── libs/
│   ├── core/                   # Domain (zero framework deps)
│   │   └── src/core/
│   │       ├── domain/entities/
│   │       ├── domain/value_objects/
│   │       ├── ports/
│   │       ├── records/
│   │       └── services/
│   └── audio/                  # Audio processing
│       └── src/audio/
│           ├── processing/
│           ├── video/
│           └── analysis/
├── sources/
│   └── t3k/                    # T3K source adapter
│       └── src/source_t3k/
│           ├── domain/
│           ├── adapters/inbound/
│           ├── adapters/outbound/
│           └── services/
├── apps/
│   ├── webapp/                 # FastAPI
│   │   └── src/webapp/
│   ├── worker/                 # TaskIQ + pgmq consumer
│   │   └── src/worker/
│   └── scheduler/              # TaskIQ scheduler
│       └── src/scheduler/
├── frontend/astro/             # Build system (pre-bundled)
├── infrastructure/
│   ├── docker/
│   ├── migrations/
│   └── nginx/
└── tests/
```

### Dependency Rules Table (add to Key Patterns)

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, sources, apps |
| `audio` | core | sources, apps |
| `source_*` | core | audio, other sources, apps |
| `webapp` | core, audio | sources |
| `worker` | core, audio | sources |
| `scheduler` | core | audio, sources |

**Critical**: Webapp has NO dependency on sources. Worker is the bridge.

### Files to Modify

- `/home/ryan/Work/guitar-tone-worktrees/main/AGENTS.md`

---

## Phase 1: Infrastructure Foundation

**Goal**: Establish uv workspace, Docker stack, databases, justfile, directory scaffolds.

### Step 1: Root Workspace Configuration

**File**: `pyproject.toml`

```toml
[project]
name = "gts"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["libs/*", "sources/*", "apps/*"]

[tool.import-linter]
root_packages = ["core", "audio", "source_t3k", "webapp", "worker", "scheduler"]

[[tool.import-linter.contracts]]
name = "core-isolation"
type = "forbidden"
source_modules = ["core"]
forbidden_modules = ["audio", "source_t3k", "webapp", "worker", "scheduler"]
# ... additional contracts for each module
```

### Step 2: Workspace Member pyproject.toml Files

| Package | Key Dependencies |
|---------|------------------|
| `libs/core` | None (zero deps!) |
| `libs/audio` | gts-core, pedalboard, nam, pyloudnorm, torch |
| `sources/t3k` | gts-core, httpx, sqlalchemy, asyncpg, pgmq |
| `apps/webapp` | gts-core, gts-audio, fastapi, uvicorn, sqlalchemy, redis, jinja2 |
| `apps/worker` | gts-core, gts-audio, taskiq, pgmq |
| `apps/scheduler` | gts-core, taskiq, redis |

### Step 3: Docker Compose

**File**: `docker-compose.yml`

Key services:
- `db`: PostgreSQL 16 with pgmq extension, initialises both databases
- `redis`: Redis 7 for sessions/cache/job broker
- `backend`: FastAPI webapp
- `nginx`: Reverse proxy
- `worker`: TaskIQ worker
- `scheduler`: TaskIQ scheduler

**Files to create**:
- `infrastructure/docker/init-db.sql` - Creates gts_core + gts_t3k_source databases
- `infrastructure/docker/init-pgmq.sql` - Enables pgmq extension, creates queues

### Step 4: justfile

Key commands:
```makefile
up-d: uv sync && docker compose up -d
check: check-lint check-types check-tests
check-lint: uv run ruff check libs/ sources/ apps/
check-types: uv run mypy libs/core/ --strict
uv-sync: uv sync --all-packages
migrate: docker compose exec backend uv run alembic upgrade head
```

### Step 5: Directory Scaffolds

Create all `__init__.py` files for:
- `libs/core/src/core/{domain,domain/entities,domain/value_objects,ports,records,services}/`
- `libs/audio/src/audio/{processing,video,analysis}/`
- `sources/t3k/src/source_t3k/{domain,adapters,adapters/inbound,adapters/outbound,services}/`
- `apps/webapp/src/webapp/{api,auth,services,adapters}/`
- `apps/worker/src/worker/{consumers,jobs}/`
- `apps/scheduler/src/scheduler/schedules/`

### Step 6: Environment Configuration

**File**: `.env.example`
- `DATABASE_URL` → gts_core
- `T3K_DATABASE_URL` → gts_t3k_source
- `REDIS_URL`
- `SECRET_KEY`, `OAUTH_ENCRYPTION_KEY`
- Storage paths

### Phase 1 Deliverables

- [ ] `uv sync` resolves all dependencies
- [ ] `docker compose up -d` starts all services
- [ ] Both databases exist with correct extensions
- [ ] `just check` passes (empty packages)
- [ ] `import-linter` passes

---

## Phase 2: Core Domain Library

**Goal**: Implement `libs/core/` with entities, value objects, ports, and domain services.

### Archive Code Evaluation

| Archive File | Verdict | Action |
|--------------|---------|--------|
| `domain/value_objects/signal_chain_enums.py` | REFACTOR | Move directly, add IR/AA_SNAPSHOT/PROTEUS platforms |
| `domain/value_objects/job_status.py` | REFACTOR | Move directly |
| `domain/value_objects/download_status.py` | REFACTOR | Move directly |
| `domain/value_objects/tone_config.py` | REFACTOR | Move directly |
| `domain/value_objects/audio_result.py` | REFACTOR | Move directly |
| `domain/entities/signal_chain.py` | PARTIAL | Extract validation to service, update for unified Gear |
| `domain/entities/user.py` | PARTIAL | Remove tone3000_id, add generic identity linking |
| `domain/entities/job.py` | REFACTOR | Move directly |
| `domain/entities/block_type.py` | REFACTOR | Move directly |
| `domain/entities/t3k_*.py` | MOVE | To `sources/t3k/domain/` |
| `domain/ports/repositories.py` | PARTIAL | Remove T3K repos, add unified GearRepository |
| `domain/ports/audio_processor.py` | REFACTOR | Move directly |

### Implementation Order

#### Step 1: Value Objects (no dependencies)

Create frozen dataclasses in `libs/core/src/core/domain/value_objects/`:

1. `signal_chain_enums.py` - GearType, Platform, EffectCategory, ModelSize, BlockPosition
2. `job_status.py` - JobStatus, JobType enums
3. `download_status.py` - DownloadStatus enum
4. `block_category.py` - BlockCategory enum
5. `audio_result.py` - AudioResult frozen dataclass
6. `video_result.py` - VideoResult frozen dataclass
7. `chapter_marker.py` - ChapterMarker frozen dataclass
8. `tone_config.py` - ToneConfig frozen dataclass
9. `processing_metadata.py` - ProcessingMetadata frozen dataclass
10. `audio_checksum.py` - AudioChecksum (SHA256 wrapper)
11. `waveform_data.py` - WaveformData

#### Step 2: Entity Base Class

**File**: `libs/core/src/core/domain/entities/base.py`

```python
@dataclass(eq=False, slots=True)
class Entity:
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __eq__(self, other): return self.id == other.id
    def __hash__(self): return hash(self.id)
```

#### Step 3: Aggregate Root Entities

Create in `libs/core/src/core/domain/entities/`:

1. `user.py` - User + UserIdentity (generic, not T3K-specific)
2. `gear.py` - Gear + GearModel + GearSource + UserGear (NEW unified model)
3. `di_track.py` - DITrack (user-uploaded recordings)
4. `signal_chain.py` - SignalChain + SignalChainBlock (adapt validation logic)
5. `shootout.py` - Shootout + ShootoutChain
6. `job.py` - Job entity
7. `block_type.py` - BlockType (built-in processor templates)
8. `signal_chain_group.py` - SignalChainGroup + related entities

#### Step 4: Port Definitions

**File**: `libs/core/src/core/ports/repositories.py`

Protocols for:
- `UserRepository` (remove get_by_tone3000_id, add get_by_identity)
- `GearRepository` (NEW - unified, includes get_by_source)
- `DITrackRepository`
- `SignalChainRepository`
- `ShootoutRepository`
- `JobRepository`
- `AuditRepository`

**File**: `libs/core/src/core/ports/audio_processor.py` - AudioProcessor Protocol
**File**: `libs/core/src/core/ports/video_composer.py` - VideoComposer Protocol

#### Step 5: Sync Record Schema

**File**: `libs/core/src/core/records/gear_sync.py`

```python
@dataclass(frozen=True)
class GearSyncRecord:
    source_name: str
    source_record_id: str
    source_updated_at: datetime
    operation: SyncOperation  # CREATE, UPDATE, DELETE
    payload: dict[str, Any]
```

Core owns this contract. Source adapters must conform to it.

#### Step 6: Domain Services

**File**: `libs/core/src/core/services/signal_chain_validator.py`
- Extract validation logic from SignalChain.validate()
- Grammar rules: NO_AMP, MULTIPLE_AMPS, IR_REQUIRED, IR_FORBIDDEN, INVALID_ORDER

**File**: `libs/core/src/core/services/permutation_calculator.py`
- Extract from archive's signal_chain_group.py
- Null gear handling for with/without comparisons
- Limit enforcement (max 27 permutations)

### Phase 2 Deliverables

- [ ] All entities importable: `from core.domain.entities import *`
- [ ] All ports importable: `from core.ports import *`
- [ ] GearSyncRecord importable: `from core.records import GearSyncRecord`
- [ ] Unit tests for domain services pass
- [ ] `import-linter` passes (no forbidden imports)
- [ ] Zero SQLAlchemy/FastAPI imports in `libs/core/`

---

## Subagent Delegation Strategy

| Task | Agent | Rationale |
|------|-------|-----------|
| AGENTS.md update | Direct (orchestrator) | Sequential text editing |
| Phase 1 scaffolds | Direct (orchestrator) | File creation, sequential |
| Phase 1 Docker/justfile | `docker-infra` skill | Infrastructure expertise |
| Phase 2 value objects | Parallel subagents | Independent, no dependencies |
| Phase 2 entities | Sequential subagents | Dependency order matters |
| Phase 2 validation | `code-reviewer` agent | Verify DDD patterns |

---

## Verification

### Pre-Task Verification
1. AGENTS.md reflects new directory structure
2. All example paths in AGENTS.md are valid
3. Dependency rules table is accurate

### Phase 1 Verification
```bash
uv sync                                    # Dependencies resolve
docker compose up -d                       # Services start
docker compose exec db psql -U gts -d gts_core -c '\dt'  # Tables exist
docker compose exec db psql -U gts -d gts_t3k_source -c "SELECT pgmq.list_queues()"  # Queues exist
just check                                 # Quality gates pass
import-linter --config pyproject.toml      # No violations
```

### Phase 2 Verification
```bash
uv run python -c "from core.domain.entities import *"   # Entities importable
uv run python -c "from core.ports import *"             # Ports importable
uv run python -c "from core.records import GearSyncRecord"  # Records importable
uv run pytest tests/unit/core/ -v                       # Unit tests pass
uv run ruff check libs/core/                            # No lint errors
uv run mypy libs/core/ --strict                         # Type checks pass
grep -r "sqlalchemy\|fastapi" libs/core/                # No framework imports
```

---

## Critical Files

### To Create
- `pyproject.toml` (workspace root)
- `libs/core/pyproject.toml`
- `libs/audio/pyproject.toml`
- `sources/t3k/pyproject.toml`
- `apps/webapp/pyproject.toml`
- `apps/worker/pyproject.toml`
- `apps/scheduler/pyproject.toml`
- `docker-compose.yml`
- `infrastructure/docker/init-db.sql`
- `infrastructure/docker/init-pgmq.sql`
- `justfile`
- `.env.example`
- All `__init__.py` scaffolds
- All `libs/core/` domain files

### To Modify
- `AGENTS.md`

### Archive References
- `backend/app/domain/entities/*.py`
- `backend/app/domain/value_objects/*.py`
- `backend/app/domain/ports/*.py`
