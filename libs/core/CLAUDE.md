# Core Bounded Context

Pure Python domain model. Zero framework dependencies. Foundation for all other modules.

## Dependencies

Can import: (none)
Cannot import: audio, video, sources, apps

## Key Patterns

- All relationships use `lazy="raise"` — no implicit loading
- Value objects are immutable dataclasses
- Repository interfaces (ports) define contracts — implementations live in webapp/worker
- Domain services contain business logic, entities contain state + invariants
- `records/` holds data-transfer types for cross-BC communication (not entities)

## Key Files

- `src/core/domain/entities/` — User, Gear, Shootout, SignalChain, Job, DITrack, BlockType
- `src/core/domain/value_objects/` — JobStatus, DownloadStatus, RenderStatus, ToneConfig, etc.
- `src/core/ports/repositories.py` — Abstract repository interfaces
- `src/core/services/signal_chain_validator.py` — Signal chain grammar validation
