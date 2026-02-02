# /ralph-hybrid-prd - Generate PRD from Spec

Generate or regenerate `prd.json` from an existing `spec.md` file.

## Arguments

- `$ARGUMENTS` - Not used. Feature folder is derived from current git branch.

## When to Use

- After manually editing `spec.md`
- To regenerate `prd.json` after adding/removing stories
- When `spec.md` exists but `prd.json` doesn't
- When `ralph-hybrid validate` reports sync errors
- To reset all `passes` fields to `false`
- To add per-story `model` or `mcpServers` configuration

## Workflow

### 1. Locate Spec

```
1. Get current git branch: git branch --show-current
2. Derive feature folder: .ralph-hybrid/{branch-name}/ (slashes → dashes)
3. Look for spec.md in that folder
4. Error if not found
```

> **Note:** User must be on the correct branch. There's no argument to specify a different feature.

### 2. Parse Spec

Read `spec.md` and extract:

| Field | Source |
|-------|--------|
| `description` | Problem Statement section (first paragraph) |
| `createdAt` | Frontmatter `created:` or current timestamp |
| `userStories` | Each `### STORY-XXX:` section |

For each story, extract:
- `id` from header (e.g., `STORY-001`)
- `title` from header (after the colon)
- `description` from "As a... I want... So that..." block
- `acceptanceCriteria` from bullet points under "Acceptance Criteria:"
- `priority` from order (first story = 1)
- `notes` from "Notes:" section (optional)
- `model` from "Model:" line (optional, e.g., `sonnet`, `opus`, `haiku`)
- `mcpServers` from "MCP Servers:" line (optional, comma-separated list)
- `spec_ref` from "Spec Ref:" line (optional, path to detailed spec)

### 3. Generate PRD

Create `.ralph-hybrid/{branch-name}/prd.json`:

```json
{
  "description": "{from Problem Statement}",
  "createdAt": "{from spec or now}",
  "userStories": [
    {
      "id": "STORY-001",
      "title": "{from spec}",
      "description": "{As a... I want... So that...}",
      "acceptanceCriteria": [
        "{criterion 1}",
        "{criterion 2}"
      ],
      "priority": 1,
      "passes": false,
      "notes": "{from Notes: or empty}",
      "model": "sonnet",
      "mcpServers": ["chrome-devtools"]
    }
  ]
}
```

#### Per-Story Configuration Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `model` | string | (global default) | Override model for this story (`sonnet`, `opus`, `haiku`) |
| `mcpServers` | array | `[]` | MCP servers to enable for this story |
| `spec_ref` | string | (none) | Path to detailed spec file for complex stories |

**When to use per-story configuration:**
- `model: "opus"` - Complex algorithms, architectural decisions, difficult debugging
- `model: "haiku"` - Simple fixes, boilerplate, straightforward CRUD
- `mcpServers: ["chrome-devtools"]` - UI debugging, visual verification
- `mcpServers: ["playwright"]` - E2E testing, browser automation
- `mcpServers: ["postgres"]` - Database schema changes, migrations

> **Note:** No `feature` or `branchName` fields. The folder path (derived from branch) is the identifier.

### 4. Initialize Progress (if needed)

If `progress.txt` doesn't exist, create it:

```
# Progress Log
# Branch: {branch-name}
# Started: {ISO-8601}
# Spec: spec.md

```

### 5. Report

```
Generated: .ralph-hybrid/feature-user-auth/prd.json

Branch: feature/user-auth
Stories: 4 total
  - STORY-001: User Registration (passes: false)
  - STORY-002: User Login (passes: false, model: opus)
  - STORY-003: Auth Middleware (passes: false, mcpServers: [chrome-devtools])
  - STORY-004: Token Refresh (passes: false)

Ready to run:
  ralph-hybrid run
```

---

## Options

### Preserve Progress Mode (default)

If `prd.json` already exists with some `passes: true`:

1. Match stories by ID
2. Preserve `passes` and `notes` for existing stories
3. Preserve `model` and `mcpServers` if not specified in spec
4. Add new stories with `passes: false`
5. **Check for orphaned stories** (in prd but not in spec)

```
Found existing prd.json with 2/4 stories complete.

Changes detected:
  ✓ STORY-001: User Registration (passes: true) → preserved
  ✓ STORY-002: User Login (passes: true) → preserved
  ✓ STORY-003: Auth Middleware (passes: false) → preserved
  + STORY-005: Password Reset (NEW)

Proceed? [Y/n]
```

### Orphaned Story Handling

If stories exist in prd.json but not in spec.md:

**Case 1: Orphaned story with `passes: false`** (no work lost)
```
⚠ Warning: STORY-004 is in prd.json but not in spec.md
  Status: passes: false (no work completed)
  Action: Will be removed from prd.json

  Continue? [Y/n]
```

**Case 2: Orphaned story with `passes: true`** (COMPLETED WORK AT RISK)
```
✗ Error: STORY-004 is in prd.json but not in spec.md
  Status: passes: true (COMPLETED)

  This represents completed work that will be DISCARDED.

  Options:
    A) Add STORY-004 back to spec.md (preserve work)
    B) Confirm removal (discard completed work)
    C) Cancel
```

This prevents accidental loss of completed work when specs are modified.

### Reset Mode

To reset all progress:

```
> "Reset all progress? This will set all passes: false"
>   A) Yes, reset all
>   B) No, preserve progress
```

### Validation

Before generating, validate:

1. **Story count**: Warn if > 10 stories (may indicate oversized feature)
2. **Criteria count**: Warn if any story has > 6 acceptance criteria
3. **Required criteria**: Warn if missing "Typecheck passes" or test criteria
4. **Story IDs**: Warn if IDs are not sequential or have gaps
5. **Model values**: Warn if model is not one of: `sonnet`, `opus`, `haiku`
6. **MCP servers**: Warn if mcpServers references unknown servers

---

## Spec Format for Per-Story Configuration

In `spec.md`, add optional fields to story sections:

```markdown
### STORY-002: Build user profile UI component

As a user, I want to view my profile so that I can see my account information.

**Model:** sonnet
**MCP Servers:** chrome-devtools
**Spec Ref:** specs/profile-ui.spec.md

**Acceptance Criteria:**
- Component renders without console errors
- Network requests to /api/user return 200
- No JavaScript exceptions in console

**Notes:** UI Development - use Chrome DevTools for debugging
```

---

## Example

```
User: /ralph-hybrid-prd

Claude: Current branch: feature/user-auth
Feature folder: .ralph-hybrid/feature-user-auth/

Reading spec.md...

Found 4 user stories:
  1. STORY-001: User Registration
  2. STORY-002: User Login (model: opus)
  3. STORY-003: Auth Middleware (mcpServers: [chrome-devtools])
  4. STORY-004: Token Refresh

Validation:
  ✓ All stories have typecheck criteria
  ✓ All stories have test criteria
  ✓ Story sizes look reasonable
  ✓ Model values are valid
  ✓ MCP server references are valid

Generated: .ralph-hybrid/feature-user-auth/prd.json

Ready to run:
  ralph-hybrid run
```

---

## Error Handling

| Error | Response |
|-------|----------|
| Not on a branch | "Error: Not on a git branch (detached HEAD). Checkout a branch first." |
| No feature folder | "No .ralph-hybrid/{branch}/ folder found. Run /ralph-hybrid-plan first." |
| No spec.md found | "No spec.md found in .ralph-hybrid/{branch}/. Run /ralph-hybrid-plan first." |
| Parse error | "Could not parse spec.md. Check format at line {N}." |
| No stories found | "No STORY-XXX sections found in spec.md." |
| Invalid model | "Warning: Unknown model '{value}' in STORY-XXX. Use: sonnet, opus, haiku" |
