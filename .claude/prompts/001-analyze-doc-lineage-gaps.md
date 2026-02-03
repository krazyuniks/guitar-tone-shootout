<objective>
Analyse the documentation lineage from reference architecture to implementation to identify gaps, inconsistencies, and weak points in the documentation flow.

This analysis will help identify which documentation needs updating and where the implementation may have drifted from the plan.
</objective>

<context>
The GTS project has undergone a greenfield rewrite with a documentation chain:

1. **REFERENCE-ARCHITECTURE** (`../wiki/REFERENCE-ARCHITECTURE.md`) - Project and technology agnostic patterns for data ingestion pipelines
2. **GTS-Technical-Architecture** (`../wiki/GTS-Technical-Architecture.md`) - Implementation-specific architecture for GTS
3. **IMPLEMENTATION.md** (`../wiki/IMPLEMENTATION.md`) - Phase-by-phase implementation plan
4. **spec.md** (`.ralph-hybrid/main/spec.md`) - Phase 3 specification with user stories
5. **prd.json** (`.ralph-hybrid/main/prd.json`) - Phase 3 execution tracking (stories, status, verification)

Archive codebase for comparison: `../../guitar-tone-worktrees-archive-20260202/main/`

Current status: Phase 3 is nearly complete (29/30 stories pass according to prd.json), but STORY-030 (Documentation Updates) is still incomplete.
</context>

<research_tasks>
Thoroughly explore the documentation chain to identify:

1. **Trace completeness** - Does each concept in REFERENCE-ARCHITECTURE flow through to GTS-Technical-Architecture?
2. **Implementation coverage** - Does IMPLEMENTATION.md cover all components from GTS-Technical-Architecture?
3. **Story traceability** - Do spec.md stories trace back to IMPLEMENTATION.md phase deliverables?
4. **Reality alignment** - Does the current codebase match what spec.md/prd.json describe?
5. **Gap identification** - What's documented but not implemented? What's implemented but not documented?

For each document pair, check:
- Are all concepts from the parent document reflected in the child?
- Are there concepts in the child that don't trace to the parent?
- Are there contradictions between documents?
</research_tasks>

<analysis_approach>
1. Read each document in the chain sequentially
2. Extract key concepts, components, and deliverables from each
3. Build a traceability matrix showing:
   - REFERENCE-ARCHITECTURE concept → GTS-Tech-Arch section
   - GTS-Tech-Arch component → IMPLEMENTATION.md phase/deliverable
   - IMPLEMENTATION.md deliverable → spec.md story
   - spec.md story → prd.json status
4. Identify orphans (present in child but not parent) and gaps (present in parent but not child)
5. Check codebase reality for key items (do files exist? do they match documentation?)
</analysis_approach>

<output_format>
Create a report with sections:

## 1. Traceability Summary
High-level matrix showing documentation flow coverage

## 2. Gaps in GTS-Technical-Architecture
Concepts from REFERENCE-ARCHITECTURE not fully addressed

## 3. Gaps in IMPLEMENTATION.md
Components from GTS-Technical-Architecture not covered by phases

## 4. Gaps in spec.md/prd.json
Deliverables from Phase 3 in IMPLEMENTATION.md not captured in stories

## 5. Reality Drift
Documented items that don't match current codebase state

## 6. Documentation Quality Issues
- Stale content (historical language vs declarative)
- Missing sections
- Contradictions

## 7. Recommendations
Prioritised list of documentation updates needed

Save analysis to: `./analyses/doc-lineage-gaps.md`
</output_format>

<verification>
Before completing:
- [ ] All five documents in the chain have been read
- [ ] At least 3 key concepts traced through the full chain
- [ ] Codebase spot-checked for at least 5 documented items
- [ ] Recommendations are specific and actionable
</verification>

<success_criteria>
- Traceability matrix exists showing documentation flow
- At least 3 specific gaps identified with evidence
- Recommendations prioritised by impact
- Analysis is useful for planning STORY-030 (Documentation Updates)
</success_criteria>
