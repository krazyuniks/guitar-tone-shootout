# Epic Workflow Rules

## Hard Constraints

- **Epics run via the stateless orchestrator** (`scripts/orchestrator.py`). It reads `plan.json`, dispatches agents, logs events to JSONL, and manages retries. No AI tokens spent on orchestration.
- **One command to ingest:** `just epic-ingest <epic_number>`
- **One command to plan:** `just epic-plan <epic_number>`
- **One command to start:** `just epic-start <epic_number>`
- **One command to resume:** `just epic-resume <epic_number>`
- **One command to check status:** `just epic-status <epic_number>`

## What the Orchestrator Does

The orchestrator (`scripts/orchestrator.py`) handles everything:
- Reads `plan.json` for story definitions, scope, and agent configuration
- Dispatches Claude Code agents with constructed prompts (model, tools, skills, MCP)
- Runs type-aware validation checkpoints between stories
- Logs all events to JSONL (crash-safe, append-only)
- Classifies failures and manages retry budget (2 attempts per checkpoint)
- Posts GitHub comments at milestone points
- Resumes from last completed event after crash

## When Asked to "Run the Epic"

1. Run `just epic-start <number>` -- that's it
2. Monitor output for failures
3. If interrupted, resume with `just epic-resume <number>`
4. Check progress with `just epic-status <number>`
5. Do NOT read story files yourself, do NOT explore the codebase, do NOT dispatch agents manually

## Anti-Patterns (NEVER DO THIS)

```bash
# BANNED -- reading plan files manually to execute stories
Read(.planning/epics/E95/plan.json)
# ... then dispatching agents based on what you read

# BANNED -- dispatching sub-agents for stories
Task(subagent_type="...", prompt="implement story 01-architecture...")

# BANNED -- using old V1 commands
just epic-sync 42
just tdd-red T43
just tdd-green T43
```

## The Only Valid Approach

```bash
just epic-ingest 95   # Fetch epic from GitHub
just epic-plan 95     # Plan: context -> scope -> plan -> verify -> gate
just epic-start 95    # Execute stories sequentially
just epic-resume 95   # Resume after crash/interruption
just epic-status 95   # Check progress from JSONL logs
```
