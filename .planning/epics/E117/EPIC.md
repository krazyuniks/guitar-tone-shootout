---
github_issue: 117
title: "Project structure: libs/ → model/, create infra/messaging/"
state: OPEN
labels: ["epic"]
fetched: 2026-02-22T00:42:50Z
---

## Summary

Rename `libs/` to `model/` and create a new `infra/messaging/` package to match
the target architecture defined in the Jobs-Architecture-and-Operations wiki page.
This is a mechanical restructuring with no functional changes — all existing
behaviour is preserved.

The rename establishes the canonical project layout that all subsequent
migration epics build upon: `model/` for domain models, `infra/` for shared
infrastructure, `apps/` for application layer.

## Observable Outcomes

- [ ] `libs/core/` renamed to `model/gts/` — Python package name changes from `core` to `gts`
- [ ] `libs/audio/` renamed to `model/audio/` — directory moves, package name unchanged
- [ ] `libs/video/` renamed to `model/video/` — directory moves, package name unchanged
- [ ] `infra/messaging/` package created with its own `pyproject.toml` (`gts-messaging`)
- [ ] Messaging code moved from `model/gts/` to `infra/messaging/`:
  - `pgmq_client.py`, `consumer_base.py` (from services/)
  - `envelope.py`, `commands.py`, `events.py` (from records/)
  - `message_bus.py` (from ports/)
- [ ] Domain services remain in `model/gts/`: `signal_chain_validator.py`, `permutation_calculator.py`
- [ ] All Python imports updated: `from core.` → `from gts.`, messaging imports → `from messaging.`
- [ ] Root `pyproject.toml` updated: workspace members, ruff known-first-party, import-linter contracts, coverage sources
- [ ] All Dockerfiles updated (COPY paths for model/, infra/)
- [ ] `docker-compose.yml` volume mounts updated
- [ ] `just check` passes (lint, types, tests)

## Decisions

- Package naming: `gts-core` → `gts-domain` (pyproject.toml name), import as `gts`
- `gts-audio` and `gts-video` package names unchanged, just directory location
- `gts-messaging` is the new infra package (import as `messaging`)
- `gear_sync.py` (GearSyncRecord) stays in `model/gts/records/` — it's a domain record, not messaging infrastructure
- `infra/messaging/` depends on `pydantic` and `sqlalchemy` only — no BC dependencies
- Import-linter: messaging is infrastructure, importable by all BCs and apps

## Regression Boundaries

- All existing tests pass without modification (beyond import path updates)
- T3K sync continues to work
- All containers start successfully
- No changes to database schema, API routes, authentication, or domain logic
- `just check` (lint + types + tests) passes
