# /epic-build - Interactive Epic Creation

Transform feature ideas into fully-specified GitHub issues through structured questioning, gray area analysis, and goal-backward planning.

## Usage

```
/epic-build              # Start new epic from scratch
/epic-build {topic}      # Start with feature description
/epic-build #{number}    # Build from existing GitHub issue
/epic-build {number}     # Build from existing GitHub issue
```

## Output

- GitHub epic issue with architecture decisions
- GitHub task issues with acceptance criteria and scope
- Issues compatible with `gh_tasks_sync.py` and TDD workflow

## After Creation

```bash
just epic-sync {epic}     # Sync to .tasks/
just epic-start {epic}    # Start TDD workflow
```

## State Persistence

Planning state saved to `.planning/epics/{slug}/`:
- `CONTEXT.md` - Locked decisions
- `GOALS.md` - Goal-backward analysis
- `TASKS.md` - Task breakdown
- `created.json` - Issue numbers

---

<epic-build>

## Architecture

This command orchestrates 5 specialized subagents:

| Phase | Agent | Model | Purpose |
|-------|-------|-------|---------|
| Context | epic-context-loader | haiku | Load wiki docs, write CONTEXT.md |
| Gray Areas | epic-gray-area-analyst | haiku | Detect areas, return questions |
| Goals | epic-goal-backward | sonnet | Derive truths, write GOALS.md |
| Tasks | epic-task-breakdown | sonnet | Break down, write TASKS.md |
| GitHub | epic-github-creator | haiku | Create issues, write created.json |

Interactive phases (Core Understanding, Gray Area Q&A, Decision Gate) run in the orchestrator.

## Startup

1. **Parse argument:**
   - If number: fetch GitHub issue with `gh issue view {n} --repo krazyuniks/guitar-tone-shootout --json number,title,body,labels`
   - If text: use as feature description
   - If empty: ask "What feature would you like to build?"

2. **Derive slug:** Convert title to kebab-case (e.g., "Contact Form" → "contact-form")

3. **Check for resume:** If `.planning/epics/{slug}/` exists, offer to resume from last checkpoint

## Phase 1: Context Loading

Spawn subagent:
```
Task(epic-context-loader, model=haiku, prompt="
  slug: {slug}
  feature_description: {description}
")
```

Report results: sources found, detected areas, relevant entities.

## Phase 2: Core Understanding (Interactive)

Ask ONE question at a time:

1. **Vision:** (skip if from GitHub issue)
   "What feature are you building? (one sentence)"

2. **User Stories:**
   "Who benefits from this feature and what can they do?"

3. **Core Priority:**
   "What's the ONE thing that must work?"

4. **Boundaries:**
   "What's explicitly out of scope?"

Append answers to CONTEXT.md under `## Core Understanding`.

## Phase 3: Gray Area Analysis

Spawn subagent:
```
Task(epic-gray-area-analyst, model=haiku, prompt="
  feature_description: {description}
  detected_areas: {from context loader}
")
```

Present multi-select to user:
```
Based on GTS architecture, I've identified these areas to discuss:

[1] Data Model - Tables, columns, relations
[2] Signal Chain - Block types, ordering, validation
[3] Frontend Layers - Astro SSG vs Jinja2 SSR vs HTMX
...

Select areas to discuss (comma-separated, or 'all'):
```

## Phase 4: Gray Area Q&A (Interactive)

For each selected area, ask questions ONE at a time.

After each area, summarise and append to CONTEXT.md:
```markdown
## Locked Decisions: {Area Name}

- {Decision 1}
- {Decision 2}
```

## Phase 5: Testing Strategy (Interactive - MANDATORY)

Before Goal-Backward, confirm test patterns:
```
## Testing Strategy

GTS uses container-first testing:

- `just test-regression` - E2E quality gate
- `just test-unit` - Isolated logic (Docker)
- `just test-integration` - Real DB (Docker)
- `just test-golden-path` - User journeys (host)
- `just tdd <path>` - TDD single test

All acceptance criteria will use `just` commands only.

Confirm? [Y/n]
```

## Phase 6: Goal-Backward Analysis

Spawn subagent:
```
Task(epic-goal-backward, model=sonnet, prompt="
  slug: {slug}
  locked_decisions: {summary from CONTEXT.md}
")
```

Present summary: truths, artifact count, test count.

## Phase 7: Task Breakdown

Spawn subagent:
```
Task(epic-task-breakdown, model=sonnet, prompt="
  slug: {slug}
")
```

Present summary: task count, groups, dependency graph.

## Phase 8: Decision Gate (Interactive)

Present options:
```
Ready to create GitHub issues?

Epic: {title}
Tasks: {count}
Dependencies: Mapped
Test specs: Complete

[1] Create issues now
[2] Review task details
[3] Add more context
[4] Start over
```

Loop until user selects "Create issues now".

## Phase 9: GitHub Issue Creation

Spawn subagent:
```
Task(epic-github-creator, model=haiku, prompt="
  slug: {slug}
  epic_title: {title}
")
```

Report results: epic URL, task URLs.

## Phase 10: Commit & Push

After issues created:
```bash
git add .planning/epics/{slug}/
git commit -m "$(cat <<'EOF'
docs(planning): Add goal-backward analysis for {title}

- GOALS.md with observable truths and artifacts
- TASKS.md with task breakdown and dependencies
- created.json with GitHub issue mapping

Epic: #{epic_number}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
git push
```

## Resume Support

Detect checkpoint based on existing files:

| Files Present | Resume Point |
|---------------|--------------|
| CONTEXT.md only | Phase 3 (Gray Areas) |
| CONTEXT.md + GOALS.md | Phase 7 (Task Breakdown) |
| CONTEXT.md + GOALS.md + TASKS.md | Phase 8 (Decision Gate) |
| All + created.json | Complete (show summary) |

## CLI UX Rules

**CRITICAL:** User is in CLI with limited screen space.

1. **ONE question at a time**
2. **Context immediately before question**
3. **Summarise after 3-5 questions**
4. **Never dump large tables then ask multiple questions**

## GitHub CLI

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

</epic-build>
