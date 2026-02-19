[GTS]|rules:{authentication,container-execution,github,testing-database}|skills:{docker-infra,gts-architecture,gts-backend-dev,gts-testing}|wiki:{api-design,design-patterns,domain-model,infrastructure,persistence,testing}

Follow project conventions in AGENTS.md.

---
## Story

**ID:** 01-database
**Name:** Single Database Consolidation
**Purpose:** Merge gts_t3k_source into gts_core with BC-prefixed tables (t3k_*). Remove dual-database configuration. All T3K staging tables live alongside core tables in one database.

### Scope
**Create:**
- `infrastructure/migrations/versions/012_merge_t3k_and_bc_prefix.py`
- `infrastructure/docker/init-core-db.sh`
- `scripts/migrate_t3k_data.py`
- `tests/integration/worker/test_single_database.py`
**Modify:**
- `docker-compose.yml`
- `docker-compose.override.yml`
- `apps/webapp/src/webapp/adapters/persistence/models/base.py`
- `sources/t3k/src/source_t3k/adapters/outbound/models.py`
- `apps/worker/src/worker/db.py`
- `tests/conftest.py`

### Implementation Notes
- Create Alembic migration 012 that: (a) creates T3K staging tables in gts_core with t3k_ prefix (t3k_packs, t3k_models, t3k_creators, t3k_tags, t3k_makes, t3k_pack_images, t3k_pack_links), (b) adds pgmq extension to gts_core if not present
- Create scripts/migrate_t3k_data.py — idempotent script to copy data from gts_t3k_source to gts_core.t3k_* tables with checkpoint tracking
- Update ALL ORM model files in apps/webapp/src/webapp/adapters/persistence/models/ — not just base.py. Each model's __tablename__ remains unchanged for core tables (no core_ prefix needed since they are the default). Source-specific models use t3k_ prefix.
- Update sources/t3k/src/source_t3k/adapters/outbound/models.py to use t3k_ prefixed table names and connect to gts_core instead of gts_t3k_source
- Update sources/t3k/src/source_t3k/adapters/outbound/repository.py to use gts_core session
- Update init-core-db.sh to include pgmq extension creation and T3K-related setup
- Remove or empty infrastructure/docker/init-t3k-db.sh (mark for deletion — the second database is no longer created)
- In docker-compose.yml remove the T3K database service/volume and T3K-related env vars. Single db service with one database.
- Update apps/worker/src/worker/dependencies.py to use single database session (remove T3K session factory)
- Update apps/worker/src/worker/consumers/gear_sync.py to read from same database
- Update apps/webapp/src/webapp/config/settings.py to remove T3K database URL
- Update tests/conftest.py fixtures to use single database connection
- Update justfile to remove psql-t3k command
- Remove sources/t3k/alembic/ directory (T3K-specific Alembic config no longer needed)
- Write tests/integration/worker/test_single_database.py verifying T3K tables accessible from same connection as core tables

### Validation Checkpoint

After this story, a **process** validation will verify:
- Alembic migration applies successfully to gts_core (evidence: command, exit_code, output_tail)
- Single database integration test passes — T3K tables queryable from gts_core (evidence: command, exit_code, output_tail)
