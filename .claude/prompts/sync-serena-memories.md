<objective>
Sync Serena MCP memory files with current project state. Read the source-of-truth
documents, compare with existing memories, and update only what's changed.
</objective>

<context>
Serena memories live in `.serena/memories/` as plain markdown files.
They provide project context to Serena's semantic code tools across sessions.

Source-of-truth documents:
- `AGENTS.md` — workflow, patterns, dependency rules, git conventions
- `DEVELOPMENT.md` — stack details, setup, project structure
- `.claude/rules/*.md` — domain-specific rules (auth, testing, frontend, etc.)
- `justfile` — available commands (run `just --list`)
- `pyproject.toml` — dependencies, tool config, workspace packages
</context>

<instructions>
1. Read all existing Serena memories: use `mcp__serena__list_memories` then `mcp__serena__read_memory` for each
2. Read the source-of-truth documents listed above
3. For each memory file, compare current content against source docs:
   - **project_overview.md** — architecture, tech stack, module layout
   - **suggested_commands.md** — just commands, dev workflows
   - **code_style.md** — conventions, patterns, dependency rules
   - **task_completion.md** — quality gates, commit format, checklist
4. Use `mcp__serena__edit_memory` for targeted updates (preferred) or `mcp__serena__write_memory` for full rewrites
5. If the project has new modules, patterns, or conventions not covered by existing memories, create new memory files
6. Print a summary of what changed and what was already current
</instructions>

<rules>
- Do NOT delete memories without asking
- Do NOT add speculative content — only what's confirmed in source docs
- Keep memories concise — they're reference material, not documentation
- Prefer edit_memory (surgical) over write_memory (full rewrite)
</rules>
