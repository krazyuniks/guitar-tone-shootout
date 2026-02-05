# GitHub Issue Templates

Templates for creating epic and task issues compatible with gh_tasks_sync.py.

---

## Epic Issue Template

```markdown
# [Epic]: {title}

## Overview

{One paragraph description of what this epic accomplishes}

## User Stories

- As a {persona}, I want to {action} so that {benefit}
- As a {persona}, I want to {action} so that {benefit}

## Architecture Decisions

### Data Model
{Table structure, relations, constraints - if applicable}

### API Contract
{Endpoints, request/response schemas, errors - if applicable}

### Jobs/Queues
{Background processing, retry logic - if applicable}

### Security
{Auth, validation, rate limiting - if applicable}

### Testing Strategy
{Unit/integration/E2E boundaries, mock strategy}

## Scope

**In scope:**
- {Feature 1}
- {Feature 2}

**Out of scope:**
- {Excluded feature 1}
- {Excluded feature 2}

## Tasks

- [ ] #{task_number} {task_title}
- [ ] #{task_number} {task_title}
- [ ] #{task_number} {task_title}

## Dependencies

{Any external dependencies or blockers}
```

---

## Task Issue Template

**CRITICAL:** This template must be parseable by `scripts/gh_tasks_sync.py`. Required sections cannot be omitted.

```markdown
# [Task]: {title}

## Objective

{2-3 sentences describing what this task accomplishes and why}

## Acceptance Criteria

- [ ] {Criterion 1 - specific, testable}
- [ ] {Criterion 2 - specific, testable}
- [ ] {Criterion 3 - specific, testable}

## Scope

**Create:**
- `{file_path_1}` - {description}
- `{file_path_2}` - {description}

**Modify:**
- `{file_path_3}` - {change description}

## Dependencies

Blocked by: #{issue_number}, #{issue_number}

## Technical Notes

- Follow existing pattern in `{reference_file}`
- {Implementation hint 1}
- {Implementation hint 2}
```

---

## Required Sections for gh_tasks_sync.py

| Section | Required | Parsing |
|---------|----------|---------|
| `## Objective` | Yes | `parse_issue_body()` extracts text |
| `## Acceptance Criteria` | Yes | Regex: `- [ ] (.+)` |
| `## Scope` | Yes | `**Create:**` and `**Modify:**` subsections |
| `## Dependencies` | No | Regex: `Blocked by: #(\d+)` |
| `## Technical Notes` | No | Passed through to task file |

---

## Labels

### Issue Type Labels
- `epic` - Tracking issue for feature group
- `task` - Implementation task

### Project Labels (required for tasks)
- `project:core` - libs/core (domain logic)
- `project:audio` - libs/audio (audio processing)
- `project:webapp` - apps/webapp (FastAPI, templates)
- `project:worker` - apps/worker (jobs, consumers)
- `project:scheduler` - apps/scheduler (cron)
- `project:t3k` - sources/t3k (T3K integration)

### Priority Labels (optional)
- `priority:high`
- `priority:medium`
- `priority:low`

---

## GitHub CLI Commands

**IMPORTANT:** Always include `--repo krazyuniks/guitar-tone-shootout` per `.claude/rules/github.md`.

### Create Epic

```bash
gh issue create \
  --repo krazyuniks/guitar-tone-shootout \
  --title "[Epic]: {Title}" \
  --label "epic" \
  --body "$(cat .planning/epics/{slug}/epic-body.md)"
```

### Create Task

```bash
gh issue create \
  --repo krazyuniks/guitar-tone-shootout \
  --title "[Task]: {Title}" \
  --label "task" \
  --label "project:{workspace}" \
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

Blocked by: #{blocker}

## Technical Notes

- {note_1}
EOF
)"
```

### Update Epic with Tasks

```bash
gh issue edit {epic_number} \
  --repo krazyuniks/guitar-tone-shootout \
  --body "$(cat .planning/epics/{slug}/updated-epic-body.md)"
```

---

## Validation

After creating issues, validate structure:

```bash
# Validate issue structure for sync compatibility
just epic-sync-validate {epic_number}

# If validation passes, sync to .tasks/
just epic-sync {epic_number}
```

**Note:** Always use `just` commands, never direct `python scripts/...` calls.

---

## Example: Complete Task Issue

```markdown
# [Task]: UserGear repository filter

## Objective

Add filter methods to UserGearRepository to support browsing gear by type. This enables the "My Gear" library page to filter by AMP, IR, PEDAL, etc.

## Acceptance Criteria

- [ ] UserGearRepository has `get_by_type(user_id, gear_type)` method
- [ ] Filter returns only gear owned by user with matching type
- [ ] Filter supports pagination (offset, limit parameters)
- [ ] Query is optimized with appropriate indexes

## Scope

**Create:**
- `apps/webapp/src/webapp/adapters/persistence/repositories/user_gear_repository.py`

**Modify:**
- `apps/webapp/src/webapp/adapters/persistence/__init__.py` - export repository

## Dependencies

Blocked by: none

## Technical Notes

- Follow existing pattern in `user_repository.py`
- Use SQLAlchemy 2.0 select() with where() clauses
- Eager load related Gear entity to avoid N+1
```
