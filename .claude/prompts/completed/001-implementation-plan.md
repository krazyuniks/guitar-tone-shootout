<objective>
Create IMPLEMENTATION.md - a comprehensive implementation plan for the GTS greenfield rewrite.

This document will serve as the master plan for rebuilding the Guitar Tone Shootout application. It will be used to:
1. Define phases in strict dependency order
2. Identify opportunities for parallel execution
3. Guide creation of Jira epics and GitHub issue relationships
4. Provide criteria for evaluating archive code reuse

The output will live in the wiki and drive all subsequent implementation work.
</objective>

<context>
GTS is being rebuilt from scratch using a new technical architecture. An archive of the previous implementation exists and may contain reusable code, but all code must be evaluated against the new architecture before adoption.

**Key constraints from your description:**
- TDD for application code (not infrastructure)
- Integration tests, no mocks, avoid "death by unit tests"
- Single "test-regression" golden path test updated per feature
- Wiki documentation updated per phase to stay aligned with codebase
- Jira epics for work chunks, GitHub issues for dependencies
</context>

<input_files>
Thoroughly read and analyse these files:

1. **Primary architecture document** (source of truth for phases):
   `/home/ryan/Work/guitar-tone-worktrees/wiki/GTS-Technical-Architecture.md`

2. **Reference architecture** (for architectural pattern guidance only):
   `/home/ryan/Work/guitar-tone-worktrees/wiki/REFERENCE-ARCHITECTURE.md`

3. **Archive codebase** (for reuse evaluation):
   `/home/ryan/Work/guitar-tone-worktrees-archive-20260202/main/`
   - Explore key directories: backend/, astro/, tests/
   - Note: Do NOT copy directly. Evaluate against new architecture.

4. **Archive wiki** (for context on previous decisions):
   `/home/ryan/Work/guitar-tone-worktrees-archive-20260202/guitar-tone-shootout-wiki/`
</input_files>

<analysis_requirements>
Perform deep dependency analysis on GTS-Technical-Architecture.md sections:

1. **Extract all architectural components** from the document
   - Infrastructure (Docker, DB, nginx)
   - Core domain entities and services
   - API layers (REST, HTML fragments)
   - Frontend components (Astro, Jinja2, HTMX)
   - Background processing (pgmq per-BC workers)
   - External integrations (T3K)

2. **Build dependency graph**
   - For each component, identify what it depends on
   - Identify what depends on it
   - Mark hard dependencies vs soft dependencies

3. **Determine phase ordering**
   - Foundation phases must complete before dependent phases
   - Group related components that can be built together
   - Identify natural phase boundaries

4. **Identify parallel execution opportunities**
   - Which phases have no shared dependencies?
   - Which phases modify different parts of the codebase?
   - What can be worked on simultaneously by multiple agents/developers?

5. **Evaluate archive code for each phase**
   - Does equivalent code exist in archive?
   - How well does it align with new architecture?
   - Refactor candidate, partial reuse, or discard?
</analysis_requirements>

<archive_evaluation_criteria>
For each phase, evaluate archive code using these criteria:

**REFACTOR (high reuse potential):**
- Core logic is sound and well-tested
- Changes needed are primarily structural (file location, imports)
- Follows patterns compatible with new architecture
- Has existing tests that can be adapted

**PARTIAL REUSE (moderate reuse):**
- Some logic can be extracted and adapted
- Requires significant modification but saves time vs rewrite
- May need new tests written

**DISCARD (rewrite preferred):**
- Incompatible with new architecture patterns
- Technical debt or anti-patterns present
- Simpler to write fresh than untangle existing code
- No tests or tests are mocks-heavy

Include archive evaluation in each phase description.
</archive_evaluation_criteria>

<document_structure>
Structure IMPLEMENTATION.md as follows:

```markdown
# GTS Implementation Plan

## Overview
[Brief summary of the rewrite approach, key principles]

## Implementation Principles
- TDD for application code (integration tests, no mocks)
- Golden path regression test updated per phase
- Wiki documentation updated per phase
- Archive code evaluated per criteria before reuse

## Dependency Graph
[Visual or textual representation of component dependencies]

## Phase Execution Overview
[Table showing all phases, dependencies, parallel groups]

| Phase | Name | Depends On | Parallel Group | Archive Reuse |
|-------|------|------------|----------------|---------------|

## Phases

### Phase 1: [Name]
**Goal:** [Single sentence goal]
**Depends on:** [List or "None - foundation"]
**Parallel group:** [A, B, C... or "Sequential"]

**Components:**
- [Component 1]
- [Component 2]

**Archive evaluation:**
- `archive/path/file.py` - [REFACTOR/PARTIAL/DISCARD] - [reason]

**Deliverables:**
- [Specific outputs]

**Regression test update:**
- [What the golden path test should verify after this phase]

**Wiki updates:**
- [Which wiki sections to update]

---

[Repeat for each phase]

## Parallel Execution Plan
[Detailed breakdown of which phases can run simultaneously]

### Wave 1 (Foundation)
- Phase 1: [name] - must complete first

### Wave 2 (Core)
- Phase 2A: [name] - parallel group A
- Phase 2B: [name] - parallel group A
- Phase 3: [name] - parallel group B (can run with 2A/2B)

[Continue waves...]

## Risk Register
[Known risks, dependencies on external systems, potential blockers]

## Appendix: Archive Code Inventory
[Summary table of archive code evaluation results]
```
</document_structure>

<output>
Save the completed document to:
`/home/ryan/Work/guitar-tone-worktrees/wiki/IMPLEMENTATION.md`
</output>

<verification>
Before declaring complete, verify:

1. **Completeness check:**
   - All sections from GTS-Technical-Architecture.md are represented in phases
   - No orphan components (everything has a phase)
   - No circular dependencies in phase ordering

2. **Dependency validation:**
   - Each phase's dependencies are listed
   - Foundation phases have no dependencies
   - Later phases only depend on earlier phases

3. **Parallel execution validity:**
   - Parallel phases don't modify the same files
   - Parallel phases don't have hidden dependencies
   - Wave groupings make logical sense

4. **Archive evaluation coverage:**
   - Key archive directories evaluated
   - Clear recommendation for each major component
   - Rationale provided for each recommendation

5. **Actionability:**
   - Each phase could become a Jira epic
   - Deliverables are concrete and measurable
   - Regression test updates are specific
</verification>

<success_criteria>
- IMPLEMENTATION.md saved to wiki folder
- All architecture sections mapped to phases
- Clear dependency ordering (no cycles)
- Parallel execution opportunities identified and grouped into waves
- Archive code evaluated with REFACTOR/PARTIAL/DISCARD recommendations
- Each phase includes regression test and wiki update guidance
- Document is immediately actionable for Jira epic creation
</success_criteria>
