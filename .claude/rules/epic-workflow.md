<!-- domains: workflow -->
# Epic Workflow Rules
- Epics run via the stateless orchestrator (`scripts/orchestrator.py`). It reads `plan.json`, dispatches agents, logs JSONL, manages retries.
- `just epic-ingest <N>` -- fetch epic from GitHub.
- `just epic-plan <N>` -- context, scope, plan, verify, gate.
- `just epic-start <N>` -- execute stories sequentially.
- `just epic-resume <N>` -- resume after crash/interruption.
- `just epic-status <N>` -- check progress from JSONL logs.
- NEVER read plan files manually, dispatch sub-agents, or use old V1 commands. The orchestrator handles everything.
