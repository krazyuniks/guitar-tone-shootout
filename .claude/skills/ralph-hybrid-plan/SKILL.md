---
name: ralph-hybrid-plan
description: Plan a new feature for Ralph Hybrid development. Guide the user through requirements gathering, specification, and PRD generation. Includes mid-implementation amendments and PRD regeneration.
---

# Ralph Hybrid Planning Skill

**Activation:** Feature planning, specification writing, PRD generation, mid-implementation amendments

**Commands:**
- `/ralph-hybrid-plan` - Full planning workflow
- `/ralph-hybrid-amend` - Mid-implementation scope changes
- `/ralph-hybrid-prd` - Regenerate prd.json from spec.md

## Arguments

- `$ARGUMENTS` - Brief description of the feature to plan (optional).

## Flags

| Flag | Description |
|------|-------------|
| `--list-assumptions` | Surface implicit assumptions before planning |
| `--research` | Spawn research agents for topic investigation |
| `--regenerate` | Regenerate prd.json from existing spec.md |
| `--no-issue` | Skip GitHub issue lookup |
| `--skip-verify` | Skip plan verification phase |
| `--legacy` | Use legacy .ralph-hybrid/ in-tree state (default: external state at ~/.ralph/) |

## Workflow Overview

```
Phase 0:   DISCOVER     -> Extract context from GitHub issue
Phase 0.5: SDLC         -> Discover project tooling
Phase 1:   SUMMARIZE    -> Combine external context with user input
Phase 1.5: ASSUMPTIONS  -> [Optional] Surface implicit assumptions
Phase 2:   CLARIFY      -> Ask targeted questions to fill gaps
Phase 2.5: RESEARCH     -> [Optional] Spawn research agents
Phase 2.7: SETTINGS     -> Collect runtime settings
Phase 3:   ANALYZE      -> Detect patterns requiring skills/scripts
Phase 4:   DRAFT        -> Generate spec.md document
Phase 5:   DECOMPOSE    -> Break spec into properly-sized stories
Phase 5.5: MUST-HAVES   -> Derive truths/artifacts/wiring per story
Phase 6:   GENERATE     -> Create prd.json for Ralph execution
Phase 7:   VERIFY       -> Run plan checker and fix issues
```

## Phase Details

### Phase 0: DISCOVER

Extract context from GitHub issue if branch was created from one.

1. Get current branch: `git branch --show-current`
2. Extract issue number from branch name patterns (e.g., `42-description`, `feature/42-description`)
3. If found, fetch via: `gh issue view 42 --json number,title,body,labels,state,comments`
4. Auto-detect research mode from keywords (research, investigate, explore, compare, etc.)

Skip conditions: branch doesn't match patterns, `gh` unavailable, `--no-issue` flag.

### Phase 0.5: SDLC

Discover project tooling and present to user. Scan for justfile/Makefile/package.json, list available commands, confirm with user.

### Phase 1: SUMMARIZE

Combine external context (issue) with user input. If resuming, read existing spec.md.

### Phase 1.5: ASSUMPTIONS (Optional, `--list-assumptions`)

Surface implicit assumptions using categorised analysis (technical, order, scope, risk, dependency). Present critical assumptions for validation.

### Phase 2: CLARIFY

Ask 3-5 targeted questions covering: problem definition, scope boundaries, success criteria, technical constraints, dependencies, UX decisions. Ask ONE question at a time.

### Phase 2.5: RESEARCH (Optional, `--research`)

Extract technical topics, spawn parallel research agents, synthesise findings. Output saved to `research/RESEARCH-{topic}.md`.

### Phase 2.7: SETTINGS

Collect: profile (quality/balanced/budget), max iterations, MCP servers, regression command, health check. Store in `config.yaml`.

**Critical distinction:** TDD tests (Claude writes during implementation) vs Regression command (runs existing tests after each story).

### Phase 3: ANALYZE

Detect patterns (framework migration, visual parity, API changes, large codebase, CSS/styling) and propose skills/scripts/callbacks.

### Phase 4: DRAFT

Generate spec.md using the template. See `references/spec-template.md` for full template.

**Feature folder derivation:**
- External state (default): `~/.ralph/projects/{repo-name}/{branch}/`
- Legacy (`--legacy`): `.ralph-hybrid/{branch-with-slashes-as-dashes}/`

### Phase 5: DECOMPOSE

Break spec into properly-sized stories. Each story completable in one Ralph iteration. Validate sizing (description 2-3 sentences, criteria <=6, files <=3).

### Phase 5.5: MUST-HAVES

Goal-backward derivation: Observable Truths -> Required Artifacts -> Key Wiring. Generate verify criteria per story.

### Phase 6: GENERATE

Create prd.json. See `references/prd-generation.md` for format. Do NOT include successCriteria in prd.json.

### Phase 7: VERIFY

Run plan checker across 6 dimensions (Coverage, Completeness, Dependencies, Links, Scope, Verification). Revision loop up to 3 iterations for BLOCKER fixes.

## Regenerate Mode

When `--regenerate`: read existing spec.md, parse stories, generate new prd.json preserving `passes` status.

## Amendment Mode

See `references/amend-workflow.md` for mid-implementation scope changes (add/correct/remove/status).

## Error Handling

- Changes after GENERATE: edit spec.md, run `--regenerate`
- Existing feature folder: resume/regenerate/fresh
- Not on feature branch: warn, suggest branch creation

## Reference Files

| File | Purpose |
|------|---------|
| `references/spec-template.md` | spec.md template with examples |
| `references/prd-generation.md` | PRD format and story structure |
| `references/amend-workflow.md` | Mid-implementation amendments |
| `references/gts-patterns.md` | GTS-specific context and patterns |
