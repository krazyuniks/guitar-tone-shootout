# Cross-Model Verification for Epic Workflow

## Context

The epic workflow currently uses only Claude models (Opus for planning, Sonnet for verification, Sonnet/Opus for implementation). This change adds Codex 5.3 GPT as a cross-model reviewer and implementer, so that no model ever marks its own homework:

- **Opus plans → Codex critiques the plan** (replaces Phase B Sonnet verifier)
- **Codex implements → Opus critiques the implementation** (new post-story gate)
- **Opus holistic review** after all stories complete (new post-epic gate)

All critique steps are **hard gates** — failure blocks the pipeline and triggers retry or exit-to-human. Every step uses fresh instances (no tainted memory).

---

## Files to Modify

| File | Change |
|------|--------|
| `workflow/dispatch.py` | Add `CodexAdapter`, adapter protocol, adapter routing, new budget defaults |
| `workflow/models.py` | Expand `AgentConfig.model` to include `"codex"` |
| `workflow/plan_verifier.py` | Phase B → Phase C: swap Sonnet for Codex critique |
| `workflow/plan_generator.py` | Update planner prompt to specify `codex` as implementation model |
| `workflow/story_executor.py` | Add post-story Opus critique with retry loop |
| `workflow/orchestrator.py` | Add agent-sync, post-epic Opus critique, enhanced JSONL |
| `workflow/jsonl_logger.py` | Add `adapter` field to universal schema, bump schema_v |
| `workflow/schemas/jsonl-events.schema.json` | New critique event types, enhanced field docs |
| `workflow/templates/critique_story.md` | **New** — story critique prompt |
| `workflow/templates/critique_epic.md` | **New** — epic holistic critique prompt |

---

## Implementation Steps

### Step 1: CodexAdapter in `dispatch.py`

**What:** Add `CodexAdapter` alongside `ClaudeAdapter`, with adapter auto-selection.

1. Add `AgentAdapter` Protocol (from `typing`):
   - `name` property → `str`
   - `build_args(model, tools, max_turns, max_budget_usd, json_schema, fallback_model, no_mcp)` → `list[str]`
   - `parse_result(completed)` → `AgentResult`

2. Add `CodexAdapter` class:
   - Binary: absolute path to `codex` via `shutil.which("codex")` with fallback to `~/.volta/bin/codex`
   - Subcommand: `exec`
   - Stdin: prompt piped via `input=` (same as Claude's `-p -`; Codex exec reads stdin when no prompt arg given)
   - Key flags: `--model gpt-5.3-codex`, `-c model_reasoning_effort="high"`, `--ephemeral`, `--json`
   - Sandbox: `--sandbox read-only` for critique, `--sandbox danger-full-access` for implementation (passed via new `sandbox` kwarg)
   - Output: `-o <tempfile>` captures last message; `--json` stdout for cost/turns parsing
   - No `--tools`, `--max-turns`, `--max-budget-usd`, `--fallback-model` (not supported by Codex CLI)
   - MCP: configured globally in `~/.codex/config.toml` — no per-invocation override needed
   - Env: strip `CLAUDECODE` (same as Claude adapter)

3. Add adapter routing:
   ```python
   ADAPTER_MAP = {"opus": _claude, "sonnet": _claude, "haiku": _claude, "codex": _codex}
   def get_adapter(model: str) -> AgentAdapter: ...
   ```

4. Update `dispatch_agent()`: auto-select adapter when `adapter is None` via `get_adapter(model)`

5. Update `dispatch_with_fallback()`: when model is `"codex"`, skip fallback logic (Codex has no fallback)

6. Add to `FALLBACK_MODELS`: `"codex": "codex"`

7. Add to `BUDGET_DEFAULTS`:
   ```python
   "critique_plan":  {"max_turns": 20, "max_budget_usd": 5.00}
   "critique_story": {"max_turns": 15, "max_budget_usd": 3.00}
   "critique_epic":  {"max_turns": 20, "max_budget_usd": 8.00}
   ```

8. Add to `TOOL_SETS`: `"critique": ["Read", "Bash", "Glob", "Grep"]`

9. Update `get_dispatch_metadata()` to include `adapter` field:
   ```python
   def get_dispatch_metadata(prompt: str, model: str, adapter_name: str = "claude") -> dict:
       return {
           "model": model,
           "adapter": adapter_name,  # "claude" or "codex"
           "prompt_hash": compute_prompt_hash(prompt),
           "prompt_tokens": estimate_tokens(prompt),
       }
   ```

**Existing functions to reuse:**
- `compute_prompt_hash()` at `dispatch.py:53` — works for any prompt
- `estimate_tokens()` at `dispatch.py:56` — works for any prompt
- `AgentResult` at `dispatch.py:59` — same return type for both adapters

### Step 2: Expand `AgentConfig.model` in `models.py`

One-line change at `models.py:57`:
```python
model: Literal["opus", "sonnet", "haiku", "codex"]
```

The JSON schema shown to the planner (via `Plan.model_json_schema()`) will automatically include `"codex"` as a valid option.

### Step 3: Phase C — Codex Plan Critique in `plan_verifier.py`

Replace Phase B Sonnet dispatch with Codex:

1. In `verify_plan()` (~line 399): change `dispatch_with_fallback(primary_model="sonnet", ...)` to `dispatch_agent(model="codex", adapter=_codex_adapter, ...)`
   - `tools=[]` (Codex uses MCP from config.toml; for critique, `sandbox="read-only"`)
   - Remove `no_mcp=True` (not applicable to Codex)
   - Budget: max_turns=20, max_budget_usd=$5.00

2. Update `_build_verifier_prompt()`: add cross-model framing — "You are a Codex agent reviewing a plan generated by Claude Opus. Your job is adversarial: find flaws, not confirm correctness."

3. Update JSONL event names: `verifier_dispatched` → also log `adapter: "codex"`, `phase_b_pass/fail` → rename to `phase_c_pass/fail` (or keep `phase_b_*` and add `adapter` field for backwards compat)

4. `verify_with_revision_cycle()` structurally unchanged:
   - Phase A deterministic ($0) → Codex critique (Phase C) → fail? → Opus revises → Phase A re-check → Codex re-critiques
   - Decision gate unchanged

### Step 4: Update Planner Prompt in `plan_generator.py`

Update `_build_planner_prompt()`:
1. Change `BUDGET_REFERENCE` table to show `codex` as the model for implementation/architecture/regression stories
2. Update `STORY_SIZING_GUIDANCE` examples to use `"model": "codex"`
3. Add note: "Codex agents receive MCP tools (Serena, Pyright, Playwright, Chrome DevTools) automatically. Do not specify tools in the agent config — they are configured globally."

### Step 5: Post-Story Opus Critique in `story_executor.py`

Insert after validation checkpoint passes, before `story_complete`:

1. Add `_run_story_critique()` function:
   - Gather git diff for story scope paths: `git diff HEAD~1 -- <scope_paths>`
   - Build critique prompt from `workflow/templates/critique_story.md`
   - Dispatch Opus in read-only mode: `dispatch_agent(model="opus", tools=["Read","Bash","Glob","Grep"], no_mcp=True, ...)`
   - Parse structured JSON result: `{"status": "pass"|"fail", "findings": [...], "summary": "..."}`
   - Log `critique_dispatched`, `critique_pass`/`critique_fail`

2. Hard gate: if critique fails, build retry context from findings and feed back into the Codex implementation retry loop. Same retry budget (2 retries) shared between validation and critique failures.

3. Log events with full cross-reference:
   ```python
   event_logger.log_event(
       "critique_dispatched",
       story_id=story_id,
       attempt=attempt,
       critique_type="story",
       critique_model="opus",
       implementation_model="codex",  # cross-reference
       adapter="claude",
       prompt_hash=...,
       prompt_tokens=...,
   )
   ```

4. On critique failure, the retry prompt includes:
   ```
   ## Critique Feedback (Attempt N)
   The following issues were identified by Opus review:
   - {finding 1 with file:line}
   - {finding 2 with file:line}
   Fix these issues and re-verify.
   ```

### Step 6: Post-Epic Opus Critique in `orchestrator.py`

Insert after all stories complete, before `epic_complete`:

1. Add agent-sync at pipeline start:
   ```python
   subprocess.run(["agent-sync", "--quiet"], cwd=PROJECT_ROOT, timeout=30)
   ```

2. Add `_run_epic_critique()` function:
   - Inputs: plan.json, EPIC.md, full git diff (`git diff <first_story_commit>..HEAD`), JSONL event summary
   - Dispatch Opus: `dispatch_agent(model="opus", tools=["Read","Bash","Glob","Grep"], no_mcp=True, max_budget_usd=8.0)`
   - Prompt from `workflow/templates/critique_epic.md`
   - Checks: observable truths achievable, user journeys supported, cross-cutting concerns

3. Hard gate: fail → `exit_to_human` with critique findings posted as GitHub comment (0 retries — too late for auto-fix)

4. Log events:
   ```python
   event_logger.log_event(
       "epic_critique_dispatched",
       critique_model="opus",
       adapter="claude",
       stories_reviewed=len(completed_stories),
       ...
   )
   event_logger.log_event(
       "epic_critique_pass",  # or epic_critique_fail
       findings_count=len(findings),
       cost_usd=result.cost_usd,
       ...
   )
   ```

### Step 7: Critique Prompt Templates

**`workflow/templates/critique_story.md`** (new):
- Role: Opus reviewer critiquing Codex implementation
- Inputs: story context, git diff, validation results
- Evidence standard: specific file:line, observed value, why it's wrong
- Exclusions: style preferences, out-of-scope issues
- Output: JSON `{"status", "findings", "summary"}`
- Findings format: `{"file", "line", "issue", "convention_violated", "severity"}`

**`workflow/templates/critique_epic.md`** (new):
- Role: Opus reviewer doing holistic post-epic review
- Checks: observable truth achievability, user journey support, cross-cutting (security, consistency, integration)
- Evidence standard: same as story critique
- Output: JSON `{"status", "findings", "summary"}`
- Findings severity: critical/major (block) vs minor (log only)

### Step 8: JSONL Schema and Logging Enhancements

**Enhanced event fields for cross-model traceability:**

Every dispatch/complete/fail event now includes:
- `adapter`: `"claude"` or `"codex"` — which CLI was used
- `model`: the specific model string (`"opus"`, `"codex"`, etc.)
- `role`: `"planner"`, `"verifier"`, `"implementer"`, `"critique_story"`, `"critique_epic"` — what role this agent played

For critique events specifically:
- `critique_type`: `"plan"`, `"story"`, `"epic"`
- `critique_model`: which model ran the critique
- `target_model`: which model produced the work being critiqued
- `target_step`: reference to the step being critiqued (e.g. `"story_id"`, `"plan_generation"`)

**New event types in schema:**

Stage 3 (Planning):
- `phase_c_dispatched` — Codex plan critique dispatched. Fields: `epic, attempt, model, adapter, prompt_hash, prompt_tokens, critique_model, target_model`
- `phase_c_pass` — Fields: `epic, attempt, scores{}, cost_usd, turns`
- `phase_c_fail` — Fields: `epic, attempt, scores{}, feedback, findings[], cost_usd, turns`

Stage 4 (Execution):
- `critique_dispatched` — Fields: `story_id, attempt, critique_type, critique_model, target_model, adapter, role, prompt_hash, prompt_tokens`
- `critique_pass` — Fields: `story_id, attempt, critique_type, critique_model, cost_usd, turns, findings_count`
- `critique_fail` — Fields: `story_id, attempt, critique_type, critique_model, findings[], cost_usd, turns`
- `critique_failed` — Fields: `story_id, attempt, critique_type, error` (dispatch infrastructure failure)
- `epic_critique_dispatched` — Fields: `critique_model, adapter, stories_reviewed, prompt_hash, prompt_tokens`
- `epic_critique_pass` — Fields: `critique_model, cost_usd, turns, findings_count`
- `epic_critique_fail` — Fields: `critique_model, findings[], cost_usd, turns`

**Update `get_resumable_state()`** in `jsonl_logger.py`:
- Recognise `critique_fail` as a retry trigger (same as `validation_fail`)
- Recognise `epic_critique_fail` as `exit_to_human`

**Bump `SCHEMA_VERSION`** from 1 to 2 (new event types added).

**Example JSONL trace for a single story (shows full cross-model flow):**
```jsonl
{"schema_v":2,"run_id":"...","ts":"...","event":"story_started","story_id":"01-model","attempt":1,"index":0}
{"schema_v":2,"run_id":"...","ts":"...","event":"agent_dispatched","story_id":"01-model","attempt":1,"model":"codex","adapter":"codex","role":"implementer","prompt_hash":"abc123","prompt_tokens":4500}
{"schema_v":2,"run_id":"...","ts":"...","event":"agent_complete","story_id":"01-model","attempt":1,"model":"codex","adapter":"codex","turns":12,"cost_usd":1.50}
{"schema_v":2,"run_id":"...","ts":"...","event":"validation_pass","story_id":"01-model","check_type":"quality","results":["just check: exit 0"]}
{"schema_v":2,"run_id":"...","ts":"...","event":"critique_dispatched","story_id":"01-model","attempt":1,"critique_type":"story","critique_model":"opus","target_model":"codex","adapter":"claude","role":"critique_story","prompt_hash":"def456","prompt_tokens":6200}
{"schema_v":2,"run_id":"...","ts":"...","event":"critique_pass","story_id":"01-model","attempt":1,"critique_type":"story","critique_model":"opus","cost_usd":0.80,"turns":5,"findings_count":0}
{"schema_v":2,"run_id":"...","ts":"...","event":"story_complete","story_id":"01-model","attempt":1,"commit":"abc1234"}
```

### Step 9: MCP Configuration for Codex

Document and configure in `~/.codex/config.toml`:

```toml
[mcp_servers.serena]
command = "npx"
args = ["-y", "@anthropic-ai/serena-mcp@latest"]

[mcp_servers.pyright]
command = "npx"
args = ["-y", "@anthropic-ai/pyright-mcp@latest"]

[mcp_servers.chrome-devtools]
command = "npx"
args = ["-y", "@anthropic-ai/chrome-devtools-mcp@latest"]
```

**Note:** Exact package names need verification — run `codex mcp add` interactively to confirm available packages. Playwright is already configured.

---

## Dependency Order

```
Step 1 (dispatch.py + CodexAdapter)  ← everything depends on this
  ├── Step 2 (models.py)             ← independent, do alongside Step 1
  ├── Step 3 (plan_verifier.py)      ← depends on Step 1
  ├── Step 4 (plan_generator.py)     ← depends on Step 2
  ├── Step 5 (story_executor.py)     ← depends on Steps 1, 7
  ├── Step 6 (orchestrator.py)       ← depends on Steps 1, 7
  ├── Step 7 (templates)             ← independent, do alongside Step 1
  └── Step 8 (JSONL schema)          ← do after Steps 3-6 (events finalised)
Step 9 (MCP config)                  ← independent, do any time
```

**Parallelisable:** Steps 1+2+7+9 can be done simultaneously.

---

## Verification

1. **Unit test the CodexAdapter:** `codex exec --json --ephemeral - <<< "say hello"` — verify output parsing
2. **Phase A still passes:** Run `just epic-validate-plan N` on an existing plan — must not regress
3. **Phase C dispatch:** Run plan verifier in isolation with Codex — verify JSON output parsing
4. **Story dispatch with Codex:** Run a single-story epic — verify Codex implements and Opus critiques
5. **JSONL trace inspection:** After a full run, `cat epic.jsonl | jq '.event'` should show the full interleaved flow: `agent_dispatched(codex) → agent_complete → validation_pass → critique_dispatched(opus) → critique_pass → story_complete`
6. **Critique failure path:** Intentionally break a story scope (wrong file path) — verify critique catches it and triggers retry
7. **Epic critique:** Run a multi-story epic to completion — verify post-epic Opus critique runs and logs
8. **`just epic-status N`** should display critique events in the status output


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/ryanlauterbach/.claude/projects/-Users-ryanlauterbach-Work-guitar-tone-shootout-worktrees-main/8a4ba572-3731-442b-9934-858733f2509a.jsonl
