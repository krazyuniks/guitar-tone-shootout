---
name: epic-github-creator
description: Create GitHub issues from TASKS.md and save mapping to created.json
model: haiku
tools:
  - Read
  - Write
  - Bash
---

# Epic GitHub Creator Agent

Template-filling agent that creates GitHub issues from task breakdown and saves the issue mapping.

## Input

Receives prompt with:
- `slug`: Epic slug for reading TASKS.md/GOALS.md and writing created.json
- `epic_title`: Title for the epic issue

## Workflow

### 1. Load Reference and Tasks

Read these files:
- `.claude/skills/epic-builder/references/github-templates.md` - Issue templates
- `.planning/epics/{slug}/TASKS.md` - Task breakdown
- `.planning/epics/{slug}/GOALS.md` - Goal-backward analysis (for epic body)

### 2. Create Epic Issue

Create the epic tracking issue:

```bash
gh issue create \
  --repo krazyuniks/guitar-tone-shootout \
  --title "[Epic]: {epic_title}" \
  --label "epic" \
  --body "$(cat <<'EOF'
# [Epic]: {epic_title}

## Overview

{Goal statement from GOALS.md}

## User Stories

{From GOALS.md observable truths}

## Architecture Decisions

{From CONTEXT.md locked decisions}

## Scope

**In scope:**
{From CONTEXT.md}

**Out of scope:**
{From CONTEXT.md}

## Tasks

(To be updated after task creation)

## Dependencies

{Any external dependencies}
EOF
)"
```

Capture the epic issue number from output.

### 3. Create Task Issues

For each task in TASKS.md, create an issue:

```bash
gh issue create \
  --repo krazyuniks/guitar-tone-shootout \
  --title "[Task]: {task_title}" \
  --label "task" \
  --label "{project_label}" \
  --body "$(cat <<'EOF'
## Objective

{objective}

## Acceptance Criteria

- [ ] {criterion_1}
- [ ] {criterion_2}
- [ ] {criterion_3}

## Scope

**Create:**
- `{path_1}`

**Modify:**
- `{path_2}`

## Dependencies

Blocked by: #{blocker_numbers}

## Technical Notes

- {note_1}
- {note_2}
EOF
)"
```

Capture each task issue number.

### 4. Update Epic with Task List

After all tasks are created, build a task checklist and append it to the epic body.

**Build the checklist** from the task numbers captured in step 3, sorted by issue number:

```
## Tasks

- [ ] #43 - FastAPI Application Skeleton
- [ ] #44 - Health Endpoints
- [ ] #45 - User ORM Model
...
```

**Append to the epic** using `--body-file` with the full updated body:

1. Read the current epic body: `gh issue view {epic_number} --repo krazyuniks/guitar-tone-shootout --json body -q '.body'`
2. Replace the placeholder `## Tasks` section (containing "(To be updated after task creation)") with the generated checklist
3. Write the updated body to `.planning/epics/{slug}/epic-body-updated.md`
4. Apply the update:

```bash
gh issue edit {epic_number} \
  --repo krazyuniks/guitar-tone-shootout \
  --body-file .planning/epics/{slug}/epic-body-updated.md
```

**This step is CRITICAL** — `epic-sync` relies on `- [ ] #N` entries in the epic body to discover child tasks. If this step is skipped, `epic-sync` falls back to label search which may return unrelated tasks.

### 5. Write created.json

Write issue mapping to `.planning/epics/{slug}/created.json`:

```json
{
  "epic": {
    "number": 42,
    "title": "[Epic]: Feature Title",
    "url": "https://github.com/krazyuniks/guitar-tone-shootout/issues/42"
  },
  "tasks": [
    {
      "id": "A1",
      "number": 43,
      "title": "[Task]: FastAPI Application Skeleton",
      "url": "https://github.com/krazyuniks/guitar-tone-shootout/issues/43",
      "labels": ["task", "project:webapp"],
      "blocked_by": []
    },
    {
      "id": "A2",
      "number": 44,
      "title": "[Task]: Health Endpoints",
      "url": "https://github.com/krazyuniks/guitar-tone-shootout/issues/44",
      "labels": ["task", "project:webapp"],
      "blocked_by": [43]
    }
  ],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## GitHub CLI Requirements

**IMPORTANT:** Always include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands per `.claude/rules/github.md`.

## Issue Templates

### Epic Body Template

Required sections:
- `## Overview` - Goal statement
- `## User Stories` - Observable truths as user stories
- `## Architecture Decisions` - Locked decisions by area
- `## Scope` - In scope / out of scope
- `## Tasks` - Checklist with issue links
- `## Dependencies` - External blockers

### Task Body Template

Required sections (for gh_tasks_sync.py compatibility):
- `## Objective` - 2-3 sentences
- `## Acceptance Criteria` - `- [ ] criterion` format
- `## Scope` - `**Create:**` and `**Modify:**` with backtick paths
- `## Dependencies` - `Blocked by: #n` or `none`
- `## Technical Notes` - Implementation hints

## Labels

| Type | Label |
|------|-------|
| Epic | `epic` |
| Task | `task` |
| Core lib | `project:core` |
| Audio lib | `project:audio` |
| Webapp | `project:webapp` |
| Worker | `project:worker` |
| Scheduler | `project:scheduler` |
| T3K source | `project:t3k` |

## Output

Returns JSON:
```json
{
  "created_file": ".planning/epics/{slug}/created.json",
  "epic_number": 42,
  "epic_url": "https://github.com/...",
  "task_count": 15,
  "tasks_created": [
    {"id": "A1", "number": 43},
    {"id": "A2", "number": 44},
    ...
  ]
}
```

## Error Handling

If a `gh` command fails:
1. Report the error
2. Return partial results with `error` field
3. Do not continue creating remaining issues

## Context Budget

Target: < 350 lines loaded into agent context
- GitHub templates: ~100 lines
- TASKS.md: varies
- GOALS.md: ~50 lines for summary
- Template filling is mechanical
