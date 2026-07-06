# ADR-0004: Shootout manifest storage and rerun

- Status: accepted
- Date: 2026-07-06
- Related: ADR-0003 (shootout comparison artefact model, which indexes this decision); ADR-0005 (shootout event-state authority, which owns the reconciliation terminal-closure that finalise depends on)
- Depends on: ADR-0003

## Context

A completed shootout's durable public artefact is a comparison manifest that the player and public pages read: the ordered signal chains, their audio segments, timing against the shared DI, and each chain's provenance. ADR-0003 fixes that this manifest is a first-class, immutable, versioned, render-time provenance snapshot, and that `shootout.status` is the authoritative public lifecycle. This ADR fixes where the manifest is stored and how a rerun behaves.

Three properties of the current code force the shape:

- Derived-on-read is unsafe. `core_shootout_chains.signal_chain_id` is `ondelete=CASCADE`, so deleting a signal chain destroys the chain rows and their `AudioSegment`s. A manifest derived from live rows at read time would 404 published media the moment an owner edits or deletes a chain, even though the rendered files still exist on disk.
- Reruns are nondeterministic against live rows. A rerun inserts a new `AudioSegment` per chain with no cleanup and no ordering, so the `segments[0]` pick in the master/montage path is undefined after the first rerun.
- Media paths overwrite in place. Renders write `<shootout_id>/<chain_id>.wav` and `master.wav` unversioned, so a rerun corrupts the exact files an existing manifest points at.

## Decision

The manifest is stored in a dedicated, insert-only table `core_shootout_manifests`, not a JSON column on `core_shootouts`. Each row is an immutable version of one shootout's manifest, uniquely identified by `(shootout_id, version)`. The payload is a self-contained JSONB snapshot with no foreign keys reaching into chains, segments, signal chains, or gear, which is what makes a published manifest immune to the signal-chain CASCADE. The field-level payload schema is owned by `docs/design/shootout-artefact-contract.md`, not this ADR.

The versioned substrate is two supporting columns: `Shootout.render_version` (a monotonic counter incremented in the run-request transaction) and `AudioSegment.version` (unique `(shootout_chain_id, version)`). All media for a run renders into a per-version directory `STORAGE_BASE/<shootout_id>/v<N>/`; a render job may only write inside its own version directory and never touches a file referenced by an existing manifest.

A new `SHOOTOUT_FINALISE` job writes the manifest at render completion. `reconcile_parent_after_audio` find-or-creates it once all audio children are COMPLETED, in the slot the master job occupies today. In one transaction the finalise handler pins this version's segment per chain, assembles the provenance snapshot, inserts the manifest row, sets `shootout.status`=COMPLETED, and completes the finalise and parent jobs. The find-or-create guard and the `(shootout_id, version)` uniqueness constraint make it exactly-once. Writing the manifest is the step that makes a shootout public, so it drives gate G1: no public link resolves without a manifest row.

Rerun semantics are owner-settled. Every run creates a new shootout; there is no in-place edit-and-rerun in v1. A published shootout's manifest is immutable and a rerun of a published shootout is blocked, which is gate G2. "Published" for the block is visibility-aware: a shootout is published once a manifest exists, `status`=COMPLETED, and `visibility` is `public` or `unlisted`. Unlisted counts as published; it is reachable and embeddable by direct non-guessable UUID and noindexed, with no auth wall in v1 (the "unlisted" definition is owned by ADR-0006). Until the visibility column lands the interim predicate is "manifest present AND COMPLETED", because the product is public-by-default and no completed shootout can safely be treated as unpublished. The guard rejects the parent run-request at the webapp handler; the uniqueness constraint is defence in depth at the finaliser. The versioned substrate and this guard stand as protection and future-proofing even though v1 exposes no rerun UX.

The `master.wav` montage is demoted (per ADR-0003) to a non-gating enrichment that runs strictly after finalise and consumes the finalise-pinned segment set, never `segments[0]`. A montage failure fails only the montage job and can never strand `shootout.status`, because the shootout is already terminal. Montage and video URLs live in the read-payload enrichment section as `{url, state}`, never inside the immutable manifest, because they complete after finalise.

## Consequences

- Immutability, versioned identity, and exactly-once finalise are database properties, not policed behaviour. There is no application UPDATE or targeted-DELETE path on `core_shootout_manifests`; the only deletion is the intentional cascade when an owner deletes the whole shootout (unpublish-by-delete).
- Published media survives signal-chain edits and deletes. The media handler resolves opaque URL -> manifest row -> version-scoped relative path -> file, gated on visibility and COMPLETED, never through `AudioSegment` rows.
- Finalise depends on the reconciliation terminal-closure owned by ADR-0005: any child reaching FAILED, DEAD_LETTERED, or CANCELLED must project the parent and shootout to FAILED. Without that closure a dead-lettered child leaves reconcile in neither branch and finalise never dispatches, which is the strand class gate G3 forbids.
- Superseded and failed version directories and rows are retained in v1; a monotonic `render_version` may leave gaps for failed runs, which is acceptable. GC and retention tooling stay deferred.
- Rejected: a JSON column on `core_shootouts` (a single slot forces overwrite-to-version, re-admitting the public-artefact mutation G2 forbids, and bloats every list row with waveform-sized payloads); a filesystem `manifest.json` beside the media (no transactional publish with the status flip, and no SQL-queryable manifest-present gate).
- ADR-0003 indexes this decision, the detailed manifest JSON schema lives in `docs/design/shootout-artefact-contract.md`, and the code lands as the manifest-table migration, the finalise job, the rerun-versioning substrate, and the montage rewire backlog units.
