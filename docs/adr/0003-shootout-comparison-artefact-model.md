# ADR-0003: Shootout comparison artefact model

- Status: accepted
- Date: 2026-07-06
- Related: ADR-0001 (app surface is a Vite + React SPA); field-level schemas live in the GTS design doc `design/shootout-artefact-contract.md`

## Context

A shootout compares several signal chains against one shared DI recording: the public product is a browse-and-play A/B comparison of those chains, and the same comparison surfaces both on the public Astro page and in the app route. Both surfaces need one stable read payload per shootout.

The render pipeline produces two kinds of audio output for a shootout: a per-chain `AudioSegment` for each signal chain, and a concatenated `master.wav` that plays the chains back-to-back. A sequential montage cannot be an A/B substrate - it forces the listener through the chains in series rather than switching between them over the same source. The per-chain segments are start-aligned by construction: every chain is rendered over the same DI from t=0.

Source rows are destructible. `core_shootout_chains.signal_chain_id` is `ondelete=CASCADE`, so editing or deleting a source signal chain deletes the chain rows and their `AudioSegment`s that a live-joined public page depends on. A public artefact built by joining live source rows loses its content outright when the owner edits their gear.

## Decision

Per-chain `AudioSegment`s are the A/B comparison substrate, and the durable public artefact is an immutable versioned manifest that snapshots them.

1. **Segments are the comparison substrate.** The player loads each chain's pinned segment and plays them time-aligned over the shared DI, start-aligned from t=0. The shootout timeline duration is the maximum per-chain duration (effect and IR tails may differ).
2. **The master is demoted to a non-gating enrichment.** `master.wav` survives as an explicitly labelled sequential montage for share, download, and SEO preview, and as a probable future video input. The player never consumes it: `Shootout.output_path` never reaches a player read payload, and the master is reachable only through an explicit montage-download path.
3. **The durable public artefact is a first-class, immutable, versioned manifest** written at render completion, carrying a render-time provenance snapshot: ordered chains (label, opaque media ref, duration, waveform, integrated LUFS, peak dBFS, and a gear-provenance block list), DI descriptors, and the timeline semantics above. Optional video enrichment fields are reserved and absent in v1.
4. **Derived-on-read is rejected.** The manifest is a render-time snapshot, not a live join. The CASCADE chain destroys the rows a live-joined page would read when a source signal chain is edited or deleted; only a versioned snapshot survives source mutation and gives rerun/immutability a stable identity to publish against. Live source rows remain for the owner's edit and rerun view; the public artefact reads only the snapshot.
5. **A shootout carries at most 16 signal chains.** This cap sizes the render fan-out, the manifest, and the player UX.

## Consequences

- This ADR is the artefact frame that the sibling ADRs index: ADR-0004 (manifest storage and rerun), ADR-0005 (event-state authority), ADR-0006 (public media security), ADR-0007 (video deferral).
- The detailed field-level schemas the manifest, provenance block, and public read payload rely on are not duplicated here. They live as sections of the GTS design doc `design/shootout-artefact-contract.md`, and the sibling ADRs delegate their field-level content to the same doc.
- The public read payload and the media handler never carry `Shootout.output_path`, `file_path`, or any container path; media is served by opaque id-based URLs.
- The 16-chain cap bounds render fan-out, manifest size, and player UX for every downstream slice.
- The comparison-player and public-shootouts slices of the frontend-reshape epic consume the manifest read payload, never `master.wav`.
