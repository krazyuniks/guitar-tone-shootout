---
name: skill-writer
description: Create and maintain well-structured Claude Code skills. Use when creating, updating, or improving skills in .claude/skills/.
---

# Skill Writer

Guide for creating and maintaining Agent Skills for Claude Code.

## When to Use

- Creating a new skill
- Improving an existing skill
- Adding resources to a skill
- Updating skill-rules.json triggers

## Skill Structure

```
.claude/skills/[skill-name]/
├── SKILL.md              # Main skill file (required)
└── resources/            # Supporting files (optional)
    ├── patterns.md       # Code patterns
    ├── examples.md       # Working examples
    └── reference.md      # API reference
```

## SKILL.md Format

### Frontmatter (Required)

```yaml
---
name: skill-name          # lowercase, hyphens, max 64 chars
description: Brief description of what this skill does and when to use it. Max 1024 chars.
---
```

### Content Structure

```markdown
# Skill Title

**Activation:** Keywords that trigger this skill

## Overview
Brief explanation of the skill's purpose.

## Key Patterns
Code patterns with examples.

## Common Tasks
Step-by-step for frequent operations.

## Resources
Link to resources/ files for deep dives.
```

## Writing Effective Skills

### 1. Clear Activation Triggers

Include keywords in the description and first section:
```markdown
**Activation:** FastAPI, SQLAlchemy, async Python, database operations
```

### 2. Concise Main File

- Keep SKILL.md under 500 lines
- Put detailed reference in resources/
- Focus on "what to do" not "what it is"

### 3. Working Examples

```python
# GOOD: Complete, copy-paste ready
@router.get("/items/{id}")
async def get_item(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Item:
    item = await db.get(Item, id)
    if not item:
        raise HTTPException(status_code=404)
    return item

# BAD: Pseudocode
def get_item(id):
    # query database
    # return item
```

### 4. Progressive Disclosure

Main file → Quick patterns
Resources → Deep dives, edge cases, full API

### 5. Actionable Instructions

```markdown
# GOOD
Use `selectinload()` to eager-load relationships:
```python
stmt = select(User).options(selectinload(User.posts))
```

# BAD
Consider using eager loading for better performance.
```

## Adding to skill-rules.json

After creating a skill, add activation triggers:

```json
{
  "skillName": "my-skill",
  "description": "What this skill does",
  "triggers": {
    "keywords": {
      "message": ["keyword1", "keyword2"],
      "file_content": ["import pattern", "code pattern"]
    },
    "file_patterns": {
      "include": ["path/to/**/*.ext"],
      "exclude": ["**/node_modules/**"]
    }
  },
  "activation": {
    "mode": "standard",
    "confidence_threshold": 0.35,
    "auto_activate": true,
    "suggestion_priority": "medium"
  }
}
```

## Skill Creation Checklist

- [ ] Created `SKILL.md` with frontmatter
- [ ] Description includes trigger keywords
- [ ] Examples are complete and tested
- [ ] Under 500 lines (use resources/ for more)
- [ ] Added to `skill-rules.json`
- [ ] Tested activation with relevant prompts

## Updating Existing Skills

1. Read current SKILL.md
2. Identify what's missing or outdated
3. Update patterns to latest versions
4. Add new examples if needed
5. Update skill-rules.json if triggers changed

## This Project's Skills

| Skill | Purpose | Key Technologies |
|-------|---------|------------------|
| backend-dev | API development | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| frontend-dev | UI development | Astro, React, TanStack, Tailwind |
| playwright | Browser automation | Playwright, MCP tools |
| pipeline-dev | Audio/video processing | NAM, Pedalboard, FFmpeg |
| testing | Test development | pytest, fixtures, mocking |
| docker-infra | Container management | Docker, Docker Compose |
| skill-writer | Skill creation | This skill |
