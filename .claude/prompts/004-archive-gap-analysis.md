# Archive Gap Analysis

> **Goal:** Identify every feature, behaviour, and capability from the archived repo
> that is missing from (or incorrectly marked in) the implementation plan.

## Inputs

| Input | Path | Purpose |
|-------|------|---------|
| **Archived repo** | `../../guitar-tone-worktrees-archive-20260202/main/` | Original codebase (source of truth for features) |
| **Current repo** | `.` (this repo) | Greenfield rewrite |
| **Implementation plan** | `../wiki/IMPLEMENTATION.md` | Migration plan (what we're auditing) |
| **Target architecture** | `../wiki/GTS-Technical-Architecture.md` | How ported features should fit |

## What to Analyse

Exhaustively catalogue everything in the archived repo across these categories:

### Runtime Behaviour
- Domain logic (entities, value objects, business rules, validation)
- API endpoints (REST, webhooks, callbacks)
- UI flows (pages, forms, navigation, user journeys)
- Worker/background jobs (async tasks, message consumers)
- Scheduled jobs (cron, periodic tasks)
- Event handling (signals, pub/sub, domain events)

### Developer/Ops Capabilities
- Maintenance scripts (data fixes, cleanup, bulk operations)
- Admin tooling (management commands, admin panels)
- Migration helpers (data migration, schema migration utilities)
- Deployment tooling (build scripts, release automation)
- Monitoring/observability (health checks, metrics, logging)

## Analysis Steps

1. **Catalogue the archive** — Walk the archived repo systematically. For each file/module, record what it does. Group findings by category above.
2. **Read the implementation plan** — Parse every phase, task, and completion status from `IMPLEMENTATION.md`.
3. **Cross-reference** — For each archived capability, find its corresponding plan item. Flag anything missing.
4. **Verify completed work** — For items marked complete in the plan, check this repo to confirm the work actually exists and matches the described scope.
5. **Map to target architecture** — For each gap found, note where it would live in the new architecture (which layer, which bounded context).

## Output

Save the report to `../wiki/CODEX_GAP_ANALYSIS.md` with this structure:

### Report Structure

```markdown
# Codex Gap Analysis

## Summary
- Total archived capabilities catalogued: N
- Covered in plan: N
- Missing from plan: N
- Marked complete but not implemented: N
- Marked complete and verified: N

## Gaps: Missing from Implementation Plan
<!-- Features in archive with NO corresponding plan item -->

| # | Category | Archived Capability | Archive Location | Suggested Plan Phase | Architecture Target |
|---|----------|---------------------|------------------|---------------------|---------------------|

## Gaps: Marked Complete but Not Implemented
<!-- Plan says done, but code doesn't exist or is incomplete -->

| # | Plan Item | Expected | Actual | Status |
|---|-----------|----------|--------|--------|

## Verified Complete
<!-- Plan says done AND code confirms it — collapsed for brevity -->

<details><summary>N items verified complete</summary>
...
</details>

## Full Archive Catalogue
<!-- Every capability found, grouped by category, with plan mapping -->
```

## Before You Start

Ask me any clarifying questions before beginning the analysis. Specifically consider:
- Are there areas of the archive I consider out of scope for the rewrite?
- Should any categories be prioritised over others?
- Are there known intentional omissions from the plan?
