---
name: epic-builder
description: Interactive epic creation with GTS-specific patterns. Transforms feature ideas into fully-specified GitHub issues through structured questioning, gray area analysis, and goal-backward planning.
context: fork
---

# Epic Builder Skill

**Activation:** Epic creation, feature planning, GitHub issue generation, TDD task breakdown

**Replaces:** `.claude/agents/planner.md` (deleted)

---

## When to Use

- Planning a new feature from scratch
- Breaking down a sparse epic into tasks
- Creating GitHub issues with full specifications
- TDD task generation with proper dependencies

---

## Workflow Phases

| Phase | Mode | Purpose |
|-------|------|---------|
| Context Loading | Autonomous | Load architecture, rules, codebase map |
| Core Understanding | Interactive | User provides vision, stories, boundaries |
| Gray Areas | Interactive | User selects areas, answers questions |
| Testing Strategy | Interactive | User confirms test boundaries |
| Goal-Backward | Autonomous | Derive truths, artifacts, wiring |
| Task Breakdown | Autonomous | Generate task structure |
| Decision Gate | Interactive | User approves or revises |
| GitHub Creation | Autonomous | Create issues, validate, save state |

---

## Reference Files

| File | Purpose |
|------|---------|
| `references/question-bank.md` | GTS-specific questions for each phase |
| `references/gray-areas.md` | Detection patterns and area definitions |
| `references/goal-backward.md` | Planning guide with GTS examples |
| `references/github-templates.md` | Issue body templates for gh_tasks_sync.py |

---

## Context Sources

| Source | Path | Purpose |
|--------|------|---------|
| Architecture | `wiki/GTS-Technical-Architecture.md` | Stack, domain model |
| Agent Guide | `AGENTS.md` | Development workflow, rules |
| Auth Rules | `.claude/rules/authentication.md` | Auth patterns |
| Test Policy | `.claude/rules/testing-policy.md` | Test boundaries |
| Frontend Rules | `.claude/rules/frontend-standards.md` | Template patterns |
| GitHub Rules | `.claude/rules/github.md` | CLI requirements |

---

## State Persistence

Epic building may span sessions. State persists in `.planning/epics/{slug}/`:

| File | Purpose |
|------|---------|
| `CONTEXT.md` | Locked decisions from gray area discussion |
| `GOALS.md` | Goal-backward analysis output |
| `TASKS.md` | Task breakdown before GitHub creation |
| `created.json` | Issue numbers after creation |

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

---

## Task Quality Criteria

Each task must have:
- [ ] Clear objective (2-3 sentences)
- [ ] Specific acceptance criteria (checkboxes)
- [ ] Exact GTS file paths in scope
- [ ] Dependencies noted (`Blocked by: #n`)
- [ ] `project:{workspace}` label

**Test:** Could a different Claude instance execute this task without asking clarifying questions?

---

## Integration with TDD Workflow

After epic creation:

```bash
# Validate issue structure
python scripts/gh_tasks_sync.py krazyuniks/guitar-tone-shootout {epic} --validate

# Sync GitHub issues to .tasks/
just epic-sync {epic}

# Start TDD orchestration
just epic-start {epic}
```
