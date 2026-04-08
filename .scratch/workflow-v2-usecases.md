# Workflow V2 — Use Cases & Failure Modes

> Historical scratch note. The Python/orchestrator workflow described here is not the current plan. The old pipeline was removed from the working tree; current workflow development is tracked by GitHub issue #165 and `../wiki/Discovery-Workflow-Design.md`.
>
> Do not implement against this file.

## Architecture: Stateless Orchestrator

The orchestrator is a **Python script** (no AI tokens). It reads a JSONL log,
determines the next step, dispatches one agent, waits for it to finish.
The agent appends events to the log + commits code. The script loops.

```
story.jsonl = the single source of truth
Each agent: reads log → pre-flight → work → append events → commit → exit
Script: reads log → determines next step → dispatches agent → waits → loops
```

## JSONL Event Types

```jsonl
{"event": "plan_complete", "ts": "...", "agents": ["arch", "ui_scaffold", "validate_scaffold", "feature_ui", "validate_crud", "regression"], "acceptance_criteria": [...]}
{"event": "agent_dispatched", "ts": "...", "agent": "arch", "attempt": 1}
{"event": "preflight_pass", "ts": "...", "agent": "arch", "checks": ["plan exists", "entities defined in plan"]}
{"event": "task_complete", "ts": "...", "agent": "arch", "task": "create User entity", "files_modified": ["libs/core/src/core/domain/entities/user.py"]}
{"event": "task_complete", "ts": "...", "agent": "arch", "task": "create UserRepository", "files_modified": ["apps/webapp/src/webapp/adapters/persistence/repositories/user.py"]}
{"event": "agent_complete", "ts": "...", "agent": "arch", "commit": "abc123", "files_modified": [...], "summary": "Created User entity, repo, service, migration"}
{"event": "preflight_fail", "ts": "...", "agent": "ui_scaffold", "severity": "minor", "detail": "User entity missing email field", "action": "self_fix"}
{"event": "preflight_fail", "ts": "...", "agent": "ui_scaffold", "severity": "major", "detail": "User entity file does not exist", "action": "report"}
{"event": "validation_pass", "ts": "...", "agent": "validate_scaffold", "checks": [{"url": "/users", "status": 200}, {"url": "/users/create", "status": 200}]}
{"event": "validation_fail", "ts": "...", "agent": "validate_crud", "checks": [{"action": "create user via form", "expected": "user in DB", "actual": "form submits but no DB row created"}]}
{"event": "exit_to_human", "ts": "...", "reason": "Agent arch failed after retry", "context": "..."}
```

---

## Use Case 1: Happy Path

```
Log: [plan_complete]
Script → dispatch arch (attempt 1)
  arch: preflight ✓ (plan exists) → builds model, repo, service, migration → commits
Log: [plan_complete, dispatched:arch:1, preflight_pass:arch, task×4, agent_complete:arch]

Script → dispatch ui_scaffold (attempt 1)
  ui_scaffold: preflight ✓ (entity files exist) → builds templates, routes → commits
Log: [..., dispatched:ui_scaffold:1, preflight_pass, task×2, agent_complete:ui_scaffold]

Script → dispatch validate_scaffold (attempt 1)
  validate_scaffold: GET /users → 200 ✓, GET /users/create → 200 ✓, DOM has expected elements ✓
Log: [..., dispatched:validate_scaffold:1, validation_pass]

Script → dispatch feature_ui (attempt 1)
  feature_ui: preflight ✓ → builds forms, HTMX, detail pages → commits
Log: [..., dispatched:feature_ui:1, preflight_pass, task×3, agent_complete:feature_ui]

Script → dispatch validate_crud (attempt 1)
  validate_crud: create user ✓, read user ✓, update user ✓, delete user ✓, DB reflects all ✓
Log: [..., dispatched:validate_crud:1, validation_pass]

Script → dispatch regression (attempt 1)
  regression: writes Playwright tests against working product → commits
Log: [..., dispatched:regression:1, agent_complete:regression]

Script → next_step = "human_validation"
Script → notify human, wait
```

**Total agents: 6. Total AI orchestration tokens: 0.**

---

## Use Case 2: Minor Pre-flight Fix (downstream agent self-corrects)

```
Log: [..., agent_complete:arch]
Script → dispatch ui_scaffold (attempt 1)
  ui_scaffold: preflight check — User entity exists but missing `display_name` field
  ui_scaffold: severity=minor → fixes it, logs the fix, continues building templates → commits
Log: [..., dispatched:ui_scaffold:1, preflight_fail:minor:"added display_name to User", task×3, agent_complete:ui_scaffold]

Script → continues normally (minor fix is logged but doesn't trigger retry)
```

**Key question: what counts as "minor"?**

Proposal:
- Minor: missing field, wrong type, typo, missing import — agent can fix in <5 lines
- Major: missing file, wrong entity entirely, architectural mismatch — needs upstream agent

The agent makes the call. If it's wrong (thinks it's minor but breaks things),
the validation checkpoint catches it later.

---

## Use Case 3: Major Pre-flight Failure → Successful Retry

```
Log: [..., agent_complete:arch]
Script → dispatch ui_scaffold (attempt 1)
  ui_scaffold: preflight check — User entity file doesn't exist at all
  ui_scaffold: severity=major → STOP, report

Log: [..., dispatched:ui_scaffold:1, preflight_fail:major:"libs/core/.../user.py does not exist"]

Script: sees preflight_fail:major for ui_scaffold
  → looks up: which agent was supposed to produce this? → arch
  → checks: arch retry count? → 0 (hasn't been retried yet)
  → re-dispatches arch with feedback: "ui_scaffold reports: User entity file missing"

Script → dispatch arch (attempt 2, with feedback)
  arch: reads feedback → "oh, I forgot to create the entity file" → creates it → commits

Log: [..., dispatched:arch:2, preflight_pass, task×1, agent_complete:arch]

Script → dispatch ui_scaffold (attempt 1 again, fresh)
  ui_scaffold: preflight ✓ → proceeds normally
```

**The feedback is the key.** Attempt 2 of arch gets:
- Original plan context
- The failure report from ui_scaffold (what was missing, what was expected)
- Its own previous log entries (what it thought it did)

---

## Use Case 4: Major Failure → Retry Fails → Exit to Human

```
Log: [..., agent_complete:arch]
Script → dispatch ui_scaffold (attempt 1)
  ui_scaffold: preflight major failure — entity structure completely wrong

Log: [..., preflight_fail:major:ui_scaffold]

Script → dispatch arch (attempt 2, with feedback)
  arch: tries to fix but still produces wrong structure

Log: [..., agent_complete:arch:attempt2]

Script → dispatch ui_scaffold (attempt 2)
  ui_scaffold: preflight STILL fails — same issue or new issue

Log: [..., preflight_fail:major:ui_scaffold:attempt2]

Script: retry count for this failure path >= 1 → EXIT TO HUMAN

Log: [..., exit_to_human:"arch cannot produce valid domain model after retry. Likely planning failure."]

Script: prints summary, shows log tail, exits
```

**Human reviews the log, sees:**
- What arch produced (via git diff)
- What ui_scaffold expected (from the failure report)
- The mismatch → probably a planning issue (entities specified wrong, or plan ambiguous)

Human fixes the plan, re-runs from the failed step.

---

## Use Case 5: Validation Failure → Fix Agent → Re-validate

```
Log: [..., agent_complete:ui_scaffold]
Script → dispatch validate_scaffold (attempt 1)
  validate_scaffold: GET /users → 200 ✓, GET /users/create → 404 ✗

Log: [..., validation_fail:validate_scaffold:{url:"/users/create", expected:200, actual:404}]

Script: sees validation_fail
  → dispatches a fix agent with the failure details

Script → dispatch fix_scaffold (attempt 1)
  fix_scaffold: reads failure → route missing in FastAPI → adds route → commits

Log: [..., dispatched:fix_scaffold:1, agent_complete:fix_scaffold]

Script → re-dispatch validate_scaffold (attempt 2)
  validate_scaffold: all checks pass ✓

Log: [..., validation_pass:validate_scaffold:attempt2]

Script → proceeds to feature_ui
```

---

## Use Case 6: Validation Keeps Failing → Exit

```
Log: [..., agent_complete:feature_ui]
Script → dispatch validate_crud (attempt 1)
  validate_crud: create user → form submits but no DB row created

Log: [..., validation_fail:validate_crud]

Script → dispatch fix_crud (attempt 1)
  fix_crud: finds form action URL wrong → fixes → commits

Script → dispatch validate_crud (attempt 2)
  validate_crud: create user → DB row created ✓, but wrong data (name field empty)

Log: [..., validation_fail:validate_crud:attempt2]

Script: validation failed twice → EXIT TO HUMAN

Log: [..., exit_to_human:"CRUD validation failed after fix attempt. Form creates DB row but data incomplete."]
```

**Two validation failures ≠ two retries of the same thing.** The fix agent changed
something, but the validation found a *different* issue. Should the script be smarter here?

Options:
a) Simple: 2 failures total = exit (current model, conservative)
b) Smarter: 2 failures of the SAME check = exit, but new failures get fresh retries
c) Budget-based: each story gets N total fix attempts across all checkpoints

Recommendation: start with (a), graduate to (b) if (a) exits too aggressively.

---

## Use Case 7: Agent Discovers Planning Failure Mid-Work

```
Log: [..., dispatched:feature_ui:1]
  feature_ui: building forms for User CRUD
  feature_ui: acceptance criteria say "user can upload avatar"
  feature_ui: but there's no file upload infrastructure, no storage config, no avatar field
  feature_ui: this isn't a minor fix — it's missing from the architecture entirely
  feature_ui: STOP → report planning failure

Log: [..., planning_failure:feature_ui:"acceptance criteria include avatar upload but no infrastructure exists for file storage. Plan needs revision."]

Script: sees planning_failure → EXIT TO HUMAN immediately (no retry)
```

**Planning failures are distinct from execution failures.**
An execution failure means "the agent didn't do what the plan said."
A planning failure means "the plan doesn't make sense given the codebase."
No amount of retrying will fix a planning failure.

---

## Use Case 8: Agent Commits Broken Code

```
Log: [..., agent_complete:arch]
Script → dispatch ui_scaffold
  ui_scaffold: preflight — entity files exist ✓
  ui_scaffold: starts building templates
  ui_scaffold: tries to import User entity → ImportError (arch committed a syntax error)

Two options:
a) ui_scaffold's preflight was too shallow — it checked file existence but not validity
b) This is a "minor fix" — ui_scaffold fixes the syntax error and continues

Recommendation: preflight should include a basic validity check:
- For Python files: import succeeds (quick `python -c "import ..."`)
- For templates: file parses
- For migrations: alembic check passes

If validity check fails → treat as major preflight failure → retry upstream agent.
```

---

## Use Case 9: Regression Tests Fail Against "Working" Product

```
Log: [..., validation_pass:validate_crud]
Script → dispatch regression (attempt 1)
  regression: writes Playwright test for user creation
  regression: test fails — form works in browser but Playwright can't find submit button
  regression: this is a test authoring problem, not a product problem

Two interpretations:
a) The product is broken (validation was wrong)
b) The test is wrong (validation was right, test needs fixing)

The regression agent should:
1. Run the test
2. If it fails, check: does manual validation still pass?
3. If manual validation passes → fix the test
4. If manual validation fails → the product regressed, report as validation failure
```

---

## Decision Matrix

| Failure type | Action | Max retries | Exit condition |
|-------------|--------|-------------|----------------|
| preflight_minor | Self-fix + log | N/A | N/A (continues) |
| preflight_major | Retry upstream agent with feedback | 1 | 2nd failure exits to human |
| validation_fail | Dispatch fix agent + re-validate | 1 | 2nd validation failure exits |
| planning_failure | Exit immediately | 0 | Always exits |
| broken_commit | Retry upstream agent (preflight catches) | 1 | Same as preflight_major |
| regression_test_fail | Agent self-diagnoses: test bug vs product bug | 1 | Unresolvable exits |

---

## Open Questions

1. **Minor vs major threshold** — should we give agents a line-count heuristic (>5 lines = major)?
   Or let the agent judge based on whether the fix is in its domain?

2. **Budget cap** — should each story have a max total agent invocations?
   (e.g., 10 agents max including retries, then exit regardless)

3. **Parallel agents** — can arch build multiple independent entities in parallel?
   Or does sequential ordering matter for dependency reasons?

4. **Fix agent vs retry** — when validation fails, should we dispatch a "fix agent"
   (new agent, reads failure, makes targeted fix) or re-dispatch the original
   implementation agent with feedback? Fix agent is cheaper (targeted context).

5. **Log pruning for agent context** — should agents read the full log or just
   relevant entries? A long story with many retries could have a huge log.
