---
github_issue: 117
title: "Event-driven architecture migration (pgmq, BC containers)"
state: OPEN
labels: []
fetched: 2026-02-19T21:01:17Z
---

## Epic: Jobs & Event-Driven Architecture Migration

Migrate from monolithic worker with TaskIQ/Redis to event-driven architecture with one container per bounded context, pgmq-only messaging, and transactional outbox.

### Key deliverables

- Single database (merge `gts_t3k_source` into `gts_core`)
- BC-prefixed tables (`core_*`, `t3k_*`)
- Project structure rename (`libs/` → `model/`, new `infra/messaging/`)
- pgmq command/event messaging with transactional outbox
- Per-BC containers: `t3k-sync`, `audio-worker`, `video-worker`
- Remove: TaskIQ, Redis, monolithic worker, scheduler

### References

- **Implementation plan:** `docs/plans/2026-02-19-jobs-event-driven-architecture-plan.md` (48 tasks, 9 phases)
- **Wiki (source of truth):** [Jobs-Architecture-and-Operations](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Jobs-Architecture-and-Operations)
- **Design rationale:** `docs/plans/2026-02-19-jobs-event-driven-architecture-design.md`

### Phases

| Phase | Tasks | Deliverable |
|-------|-------|-------------|
| 0 | 4 | Documentation baseline |
| 0.5 | 2 | Project structure: `libs/` → `model/`, new `infra/messaging/` |
| 1 | 14 | Single database, BC-prefixed tables |
| 2 | 7 | Message schemas, consumer base classes |
| 3 | 6 | T3K sync container, scheduler removed |
| 4 | 3 | Audio BC container |
| 5 | 3 | Video BC container |
| 6 | 3 | Webapp pgmq dispatch |
| 7 | 6 | Cleanup: remove TaskIQ, Redis, monolithic worker |
| **Total** | **48** | **Event-driven architecture fully operational** |
