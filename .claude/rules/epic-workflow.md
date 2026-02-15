<!-- domains: workflow -->
# Epic Workflow Rules
- Epics run via the stateless orchestrator (`workflow/orchestrator.py`). It reads `plan.json`, dispatches agents, logs JSONL, manages retries.
- `just epic N` — full pipeline: ingest -> plan -> verify -> gate -> execute.
- `just epic-status N` — check progress from JSONL logs (read-only).
- `just epic-validate-plan N` — run Phase A deterministic validation only (read-only).
- `just map-codebase` — regenerate .planning/codebase/ files.
- `just index-wiki` — regenerate .planning/wiki-indexes/.
- NEVER read plan files manually, dispatch sub-agents, or use old V1/V2 commands. The orchestrator handles everything.
