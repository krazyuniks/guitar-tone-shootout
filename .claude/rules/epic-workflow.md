<!-- domains: workflow -->
# Epic Workflow Rules
- Epics run via the stateless orchestrator (`workflow/orchestrator.py`). It reads `plan.json`, dispatches agents, logs JSONL, manages retries.
- `./wf epic run N` — full pipeline: ingest -> context -> scope -> plan -> verify -> gate -> execute.
- `./wf epic status N` — check progress from JSONL logs (read-only).
- `./wf epic validate-plan N` — run Phase A deterministic validation only (read-only).
- `./wf map codebase` / `just map-codebase` — regenerate .planning/codebase/ files.
- `./wf map wiki` / `just index-wiki` — regenerate .planning/wiki-indexes/.
- NEVER read plan files manually, dispatch sub-agents, or use old V1/V2 commands. The orchestrator handles everything.
