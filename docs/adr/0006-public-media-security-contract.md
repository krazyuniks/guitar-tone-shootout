# ADR-0006: Public media security contract

- Status: accepted
- Date: 2026-07-06
- Related: ADR-0003 (shootout comparison artefact model, which indexes the artefact/lifecycle/media ADR set), ADR-0004 (shootout manifest storage and rerun), ADR-0005 (shootout event-state authority)
- Depends on: ADR-0005 (the `shootout.status` lifecycle and the `visibility` column it defines)

## Context

ADR-0001 puts the public shootout pages on the Astro SSG surface: static browse-and-play pages that reach anonymous visitors and carry SEO/AdSense content. Serving generated audio to that surface opens a leakage surface the app has never had, because no public media path exists today - both streaming endpoints (`/audio/master`, `/chains/{id}/audio`) are owner-only and 404 everyone else, and the only capability route (`/api/files/{signature}`) is HMAC-signed capability-by-possession: expiring signatures cannot be baked into static Astro output, and non-expiring ones are permanent bearer tokens that survive a visibility change. That primitive is wrong for a public surface.

Two authorities are already settled by ADR-0005 and orthogonal: `shootout.status` (the five-state lifecycle) and the `visibility` column (`public | unlisted | private`), never inferred from each other. ADR-0004 makes the immutable, version-scoped manifest the sole durable resolution substrate for public media, because `core_shootout_chains.signal_chain_id` is `ondelete=CASCADE` - resolving public media through live `AudioSegment` rows lets an owner edit or delete published media into a 404, and `segments[0]` is non-deterministic after a rerun.

This ADR is the security-facing consolidation of those decisions: the rules that stop private rows and server-internal paths leaking once a public surface exists. It adds no new authority or schema. One live leak already exists and is remediated here: `file_path` in the DITrack response schema (`apps/webapp/src/webapp/api/v1/schemas/di_track.py`).

## Decision

Public media serving is governed by a single joint gate, opaque manifest-only resolution, and an allow-list wire payload. This is gate G4 of the shootout artefact contract.

- **Joint public gate, enforced per surface.** A shootout's media and page are served only when `(visibility = public, or visibility = unlisted addressed by direct id) AND shootout.status = COMPLETED AND a manifest row exists`. The predicate is evaluated independently and per request at each public surface - the SQL listing/browse queries, the read-payload endpoint, and the media handler - so no surface relies on another having checked. A bug at any one surface degrades to invisibility (a 404), never to leakage. Private shootouts require owner auth under the existing ownership discipline.

- **Opaque, manifest-only media resolution.** Media identity on the wire is opaque ids only; URLs encode no filesystem information (no path, storage layout, version directory, or file-derived extension), and the handler never accepts client-supplied path input. Per-chain segment media resolves through manifest-pinned segment entries; montage and video resolve by opaque id to the version-scoped enrichment pointers bound to the published render version (ADR-0004), never through live `Shootout.output_path` / `Shootout.video_path`. Resolution runs opaque id -> pinned entry -> version-scoped storage-relative path -> `STORAGE_BASE` containment check -> stream. Any gate failure - private, non-existent, not-COMPLETED, or manifest-absent - returns the same uniform 404 at both page and media handler, with no status-code or timing disclosure. The raw manifest JSONB is never serialised to any endpoint.

- **Allow-list wire payload.** The public payload is an allow-list projection of the manifest, not a redaction of internal rows: only whitelisted fields reach the wire, so the exclusion set is enforced by absence rather than trust. One payload shape serves both the Astro island and the app route; owner-only data stays on the authenticated endpoints. Every storage-relative path (`file_path`, `output_path`, `result_path`, `video_path`) and every job-internal field (`JobStatus`, job ids, `video_job_id`, `task_id`, `error`, attempt/retry fields, raw `video_status` strings) is excluded from all payloads, public and app alike. The confirmed `file_path` leak in the DITrack response schema (`apps/webapp/src/webapp/api/v1/schemas/di_track.py`) is removed, and a response-schema sweep plus an invariant test enforce the exclusion. The exact field allow-list is specified in the design doc `design/shootout-artefact-contract.md`.

- **Unlisted is reachable-by-direct-link.** `unlisted` counts as published for the rerun block, is excluded from all listings, browse queries, sitemaps, and feeds, is served only by direct id, is noindexed (`X-Robots-Tag: noindex`), and is embeddable by direct UUID. Its safety rests on id non-guessability (UUIDs, never sequential ids). There is no separate auth wall for unlisted in v1.

- **No static bypass of the gated handler.** nginx exposes no static location over the `/app/storage` mount that bypasses the handler; all public media is served through the gated handler. Serving is origin-only in v1 with no long-lived public caching, since visibility is revocable; private media is never cacheable.

## Consequences

- Public shootout media is build-correct from day one: the only remediation is the DITrack `file_path` removal and the response-schema sweep. The existing owner-only streaming endpoints and the signed-file route stay owner-only and are neither reused nor relaxed for the public surface; the public handler is new and additive.
- The public media handler is a new backlog unit gated on the visibility authority (ADR-0005) and the manifest table (ADR-0004); payload hygiene (the DITrack fix and sweep) can land immediately because it does not depend on visibility. The nginx bypass review and per-visibility cache/`X-Robots-Tag` headers are a separate unit.
- Public shootout pages may not link generated media until every gate G4 prerequisite lands together: the visibility column and SQL filters, the opaque-id media handler, payload hygiene, the ADR-0004 published-media-immutability prerequisites, and the nginx bypass review with uniform-404 semantics.
- Endpoint and URL shapes, the media-handler implementation (Range support, content types, streaming), the visibility migration, and the field-by-field response schemas are implementation detail deferred to the owning backlog units; only the resolution chain, the no-path rule, the joint gate, and the exclusion set are contract here.
- Gear icon/image assets referenced by the manifest are confirmed catalogue-public (carrying no private `user_gear` data) or routed through the same gated handler as part of the nginx review.
