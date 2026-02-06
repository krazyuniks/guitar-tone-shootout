# PRD Generation Format and Story Structure

## PRD JSON Format

```json
{
  "description": "{from spec Problem Statement}",
  "createdAt": "{ISO-8601}",
  "profile": "{quality|balanced|budget}",
  "userStories": [
    {
      "id": "STORY-001",
      "title": "{from spec}",
      "description": "{As a... I want... So that...}",
      "acceptanceCriteria": [
        "{criterion 1}",
        "{criterion 2}",
        "Typecheck passes",
        "Unit tests pass"
      ],
      "priority": 1,
      "passes": false,
      "notes": "",
      "model": "opus",
      "mcpServers": ["playwright"],
      "verify": {
        "command": "{story-specific verification command}",
        "expected": "{what success looks like}",
        "artifacts": ["{required files with line thresholds}"],
        "wiring": ["{connections that must exist}"]
      }
    }
  ]
}
```

**IMPORTANT:** Do NOT include `successCriteria` in prd.json. Success criteria is a runtime configuration set via config.yaml or CLI flag.

**Per-story config fields are optional.** Only include `model` if overriding the default. Only include `mcpServers` if the story needs specific MCP tools (or `[]` to explicitly disable MCP).

No `feature` or `branchName` fields -- the feature is identified by the folder path derived from the git branch.

## Per-Story Configuration Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `model` | string | (global default) | Override model for this story |
| `mcpServers` | array | `[]` | MCP servers to enable |
| `spec_ref` | string | (none) | Path to detailed spec file |

**When to use:**
- `model: "opus"` - Complex algorithms, architectural decisions
- `model: "haiku"` - Simple fixes, boilerplate, CRUD
- `mcpServers: ["chrome-devtools"]` - UI debugging
- `mcpServers: ["playwright"]` - E2E testing

## MCP Configuration

Three modes per story:

1. **No `mcpServers` field**: Uses epic-level MCP config from SETTINGS phase
2. **`mcpServers: []`**: Explicitly disables all MCP
3. **`mcpServers: ["specific"]`**: Override with specific servers

## Parsing spec.md

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
- `model` from "Model:" line (optional)
- `mcpServers` from "MCP Servers:" line (optional, comma-separated)
- `spec_ref` from "Spec Ref:" line (optional)

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

## Preserve Progress Mode (default)

If `prd.json` already exists with some `passes: true`:

1. Match stories by ID
2. Preserve `passes` and `notes` for existing stories
3. Preserve `model` and `mcpServers` if not specified in spec
4. Add new stories with `passes: false`
5. Check for orphaned stories (in prd but not in spec)

### Orphaned Story Handling

**Orphaned with `passes: false`** (no work lost): warn and remove.

**Orphaned with `passes: true`** (completed work at risk):
```
Options:
  A) Add STORY-004 back to spec.md (preserve work)
  B) Confirm removal (discard completed work)
  C) Cancel
```

## Reset Mode

To reset all progress, confirm with user before setting all `passes: false`.

## Validation

Before generating, validate:

1. **Story count**: Warn if > 10 stories
2. **Criteria count**: Warn if any story has > 6 acceptance criteria
3. **Required criteria**: Warn if missing "Typecheck passes"
4. **Story IDs**: Warn if not sequential or have gaps
5. **Model values**: Warn if not one of: `sonnet`, `opus`, `haiku`
6. **MCP servers**: Warn if references unknown servers

## Progress Initialisation

If `progress.txt` (legacy) or `progress.log` (external) doesn't exist, create it:

```
# Progress Log
# Branch: {branch-name}
# Started: {ISO-8601}
# Spec: spec.md
```

## Error Handling

| Error | Response |
|-------|----------|
| Not on a branch | "Error: Not on a git branch (detached HEAD)." |
| No feature folder | "Run /ralph-hybrid-plan first." |
| No spec.md found | "Run /ralph-hybrid-plan first." |
| Parse error | "Could not parse spec.md. Check format at line {N}." |
| No stories found | "No STORY-XXX sections found in spec.md." |
| Invalid model | "Warning: Unknown model '{value}'." |
