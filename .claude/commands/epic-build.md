# /epic-build - Interactive Epic Creation

Transform feature ideas into fully-specified GitHub issues through structured questioning, gray area analysis, and goal-backward planning.

## Usage

```
/epic-build              # Start new epic from scratch
/epic-build {topic}      # Start with feature description
/epic-build #{number}    # Build from existing GitHub issue
/epic-build {number}     # Build from existing GitHub issue
```

## What This Does

1. **Loads GTS context** - Architecture, patterns, conventions
2. **Asks structured questions** - Vision, user stories, boundaries
3. **Analyses gray areas** - Domain-specific decisions (signal chain, gear, etc.)
4. **Performs goal-backward analysis** - Derives truths, artifacts, tests
5. **Generates GitHub issues** - Epic + tasks with full specs

## Output

- GitHub epic issue with architecture decisions
- GitHub task issues with acceptance criteria and scope
- Issues compatible with `gh_tasks_sync.py` and TDD workflow

## After Creation

```bash
# Validate issue structure
python scripts/gh_tasks_sync.py krazyuniks/guitar-tone-shootout {epic} --validate

# Sync to .tasks/
just epic-sync {epic}

# Start TDD workflow
just epic-start {epic}
```

## State Persistence

Planning state saved to `.planning/epics/{slug}/`:
- `CONTEXT.md` - Locked decisions
- `GOALS.md` - Goal-backward analysis
- `TASKS.md` - Task breakdown
- `created.json` - Issue numbers

## Related

- `/plan` - Iterative epic planning for existing issues
- `.claude/agents/epic-builder.md` - Agent implementation
- `.claude/skills/epic-builder/` - Reference files

---

<epic-build>

## Instructions

You are the Epic Builder orchestrator. Your job is to guide the user through interactive epic creation.

### Startup

1. Load project context (autonomous):
   - Read `../wiki/IMPLEMENTATION.md` - **Phase scope, archive mappings, deliverables**
   - Read `../wiki/GTS-Technical-Architecture.md` - **Stack, domain model, testing strategy**
   - Read `AGENTS.md` - Development workflow
   - Check `.planning/codebase/` for existing analysis
   - Report what was found

2. If argument is a number (e.g., `1`, `#1`, `42`):
   - Fetch the GitHub issue: `gh issue view {number} --repo krazyuniks/guitar-tone-shootout --json title,body,labels`
   - Use issue title as the feature vision
   - Use issue body as existing context
   - **Cross-reference with `../wiki/IMPLEMENTATION.md`** for the phase's authoritative scope
   - Report what was found in the issue
   - Skip to Phase 3 (Gray Areas) - we already have the feature description

3. Check for existing state:
   - If `.planning/epics/{slug}/` exists with partial state, offer to resume
   - Otherwise, start fresh

### Workflow Phases

| Phase | Mode | Your Action |
|-------|------|-------------|
| Context Loading | Autonomous | Read wiki docs, report findings |
| Core Understanding | Interactive | Ask vision, stories, priority, boundaries |
| Gray Areas | Interactive | Present multi-select, deep-dive each |
| **Testing Strategy** | **Interactive** | **Confirm test patterns from wiki (DO NOT SKIP)** |
| Goal-Backward | Autonomous | Derive truths, artifacts, tests |
| Task Breakdown | Autonomous | Group into 15-60 min tasks |
| Decision Gate | Interactive | Present options, wait for approval |
| GitHub Creation | Autonomous | Create issues, save to created.json |
| **Commit & Push** | **Autonomous** | **Commit .planning/ changes, push to remote** |

### READ Before DERIVE (MANDATORY)

**NEVER assume data models exist. ALWAYS read the source.**

Before Goal-Backward phase, you MUST read these files **directly using the Read tool** (NO summarization agents):

1. `../wiki/GTS-Technical-Architecture.md#domain-model` - Authoritative domain model
2. `libs/core/src/core/domain/` - Actual GTS entity definitions
3. `../wiki/IMPLEMENTATION.md` - Phase scope and archive mappings

**For each artifact you derive:**
- Cite the exact file and line where the entity/field is defined
- If you cannot cite a source, **STOP and ASK**
- NEVER assume fields exist because "they make sense"

**GTS is source-agnostic.** Sources (T3K, future providers) are adapters. Core domain models NEVER contain source-specific fields (no `t3k_*`, `tone3000_*`, etc.).

### Testing Strategy Phase (MANDATORY)

Before Goal-Backward, you MUST:

1. READ `../wiki/GTS-Technical-Architecture.md#testing-strategy` section
2. READ `references/goal-backward.md` for test mapping patterns
3. Confirm test commands (ONLY `just` commands allowed):
   - `just test-regression` - E2E quality gate (stack connectivity + endpoint validation)
   - `just test-unit` - Domain logic
   - `just test-integration` - Real DB
   - `just test-e2e` - Full user journeys
   - `just tdd <path>` - Single test during TDD

**NEVER use raw `docker compose exec`, `pytest`, or `python` commands in acceptance criteria.**
**NEVER generate curl-based acceptance tests.** All tests must be pytest-based with proper locations.

### Container-First Commands (MANDATORY)

**All commands in acceptance criteria MUST use `just`.** This is a container-first architecture.

| Action | Use This | NEVER This |
|--------|----------|------------|
| Run tests | `just test-unit`, `just test-integration` | `pytest`, `python -m pytest` |
| Run E2E tests | `just test-e2e` | `cd tests/e2e && pytest` |
| Run single test | `just tdd <path>` | `docker compose exec webapp pytest` |
| Lint/type check | `just check` | `ruff check`, `mypy` |
| Build frontend | `just build-astro` | `pnpm build`, `npm run build` |

**NEVER generate raw `docker compose exec`, `python`, `pytest`, `ruff`, `mypy`, or `pnpm` commands.** Always use `just` equivalents.

### CLI UX Rules

**CRITICAL:** User is in CLI with limited screen space.

1. **ONE question at a time**
2. **Context immediately before question**
3. **Summarise after 3-5 questions**
4. **Never dump large tables then ask multiple questions**

### Gray Area Detection

Based on feature keywords, suggest relevant areas:

| Keywords | Suggested Areas |
|----------|-----------------|
| signal chain, block, amp, IR | signal_chain, gear_model |
| processing, render, audio | audio_processing, job_processing |
| sync, t3k, source | dual_database |
| page, template, form | frontend_layers |
| background, job, queue | job_processing |

### GitHub CLI

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

### Task Issue Format

**REQUIRED sections for gh_tasks_sync.py:**

```markdown
## Objective
{2-3 sentences}

## Acceptance Criteria
- [ ] {criterion 1}
- [ ] {criterion 2}

## Scope
**Create:**
- `{path}`

**Modify:**
- `{path}`

## Dependencies
Blocked by: #{number}

## Technical Notes
- {hint}
```

### Labels

- Epic: `epic`
- Task: `task`, `project:{workspace}`
- Workspaces: core, audio, webapp, worker, scheduler, t3k

### Now Begin

**If argument is a number (issue reference):**
1. Fetch the issue: `gh issue view {number} --repo krazyuniks/guitar-tone-shootout --json number,title,body,labels`
2. Display issue summary (title, key points from body)
3. Ask user to confirm or clarify the scope
4. Proceed to Phase 3 (Gray Areas)

**If argument is text (topic):**
Start with Phase 2 (Core Understanding) using that as the vision.

**If no argument:**
Ask: "What feature would you like to build?"

### Commit & Push (MANDATORY)

After GitHub issues are created and `created.json` is saved, you MUST:

1. Stage all `.planning/epics/{slug}/` files
2. Commit with message: `docs(planning): Add goal-backward analysis for {epic title}`
3. Push to remote

```bash
git add .planning/epics/{slug}/
git commit -m "$(cat <<'EOF'
docs(planning): Add goal-backward analysis for {epic title}

- GOALS.md with observable truths and artifacts
- TASKS.md with task breakdown and dependencies
- created.json with GitHub issue mapping

Epic: #{epic_number}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
git push
```

**Do NOT end the session without committing and pushing.** The planning artifacts must be available for worktree rebase.

</epic-build>
