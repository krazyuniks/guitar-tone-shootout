# Claude Code configuration

`AGENTS.md` owns project instructions. This directory contains only Claude-specific safety enforcement:

- `hooks/` blocks destructive infrastructure, mocks and edits to generated Compose overrides;
- `rules/` contains narrow command and test constraints;
- `settings.json` enables those safety hooks.

Workflow runners, prompts, merge automation, status snapshots, copied architecture and completed work do not live here.
