# Archive: 2026-01 Consolidation

Skills archived during the global consolidation effort (2026-01-30).

## Archived Skills

### software-architecture/
**Reason:** Now available globally at `~/.claude/skills/software-architecture/`

**Original location:** `.claude/skills/software-architecture/`

**Contents:**
- DDD (Domain-Driven Design)
- CQRS (Command Query Responsibility Segregation)
- Hexagonal Architecture (Ports and Adapters)
- SOLID principles
- Pythonic implementation patterns (Cosmic Python)

**Replacement:** Project now uses global skill + `python-cheatsheet` for syntax reference

---

## Migration Notes

**When moving from archive:**

1. Verify global skill exists:
   ```bash
   cat ~/.claude/skills/software-architecture/SKILL.md
   ```

2. Check for project-specific content:
   ```bash
   diff .claude/archive/2026-01-consolidation/software-architecture/SKILL.md \
        ~/.claude/skills/software-architecture/SKILL.md
   ```

3. If project-specific content found, extract to separate skill or documentation

---

**Date:** 2026-01-30
**Migrated by:** Claude Code (Documentation Writer Agent)
