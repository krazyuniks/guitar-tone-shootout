---
name: review-tests
description: Interactive test spec review for an epic — present each story's test_spec, refine with human, approve to unlock test generation.
argument-hint: "<epic-number>"
context: current
---

# Epic Test Spec Review

**Command:** `/epic review-tests <N>`

Reviews and approves test specs from a committed plan before test generation can proceed. This is an interactive CC session — the output is a `tests_approved` event in the JSONL log.

**Gate:** `plan_committed` MUST exist in `epic.jsonl`. `tests_approved` MUST NOT exist.

---

## Process

### Step 1: Validate Gates

```python
# Read the JSONL log
epic_dir = ".planning/epics/E<N>"
```

1. Read `<epic_dir>/epic.jsonl` (use Read tool)
2. Verify `plan_committed` event exists — if not, STOP: "Plan not committed. Run `just epic <N>` first."
3. Verify `tests_approved` event does NOT exist — if it does, STOP: "Tests already approved. Run `just epic <N>` to generate tests and execute."

### Step 2: Load Plan

Read `<epic_dir>/plan.json` (use Read tool). Extract all stories that have a `test_spec` field.

If no stories have test specs, tell the user and ask whether to log `tests_approved` anyway (to unblock execution).

### Step 3: Present Each Story's Test Spec

For each story with a `test_spec`, present it clearly:

```
## Story: <story_id> — <name>

**Purpose:** <purpose>

**Test type:** <test_spec.test_type>

**Fixtures:**
- <fixture_1>
- <fixture_2>

**Assertions:**
1. [<type>] <details formatted readably>
2. [<type>] <details formatted readably>
```

After presenting each story's spec, ask the human:
- "Any changes to this test spec? (fixtures, assertions, test type)"
- If yes: discuss and note the changes
- If no: move to the next story

**Rules:**
- One story at a time. Do not dump all specs at once.
- Keep assertions readable — expand the details dict into natural language.
- If a spec looks weak (e.g. only one assertion, no db_state check), flag it proactively.

### Step 4: Summarise Changes

After all stories are reviewed, present a summary:
- Number of stories with test specs
- Changes made (if any)
- Stories flagged for attention

Ask: "Approve all test specs?"

### Step 5: Apply Changes and Log Approval

On approval:

1. If any specs were changed, update `plan.json` with the refined test_specs (use Edit tool on the plan.json file)
2. Append `tests_approved` event to `epic.jsonl`:

```bash
echo '{"schema_v": 2, "run_id": "<reuse latest run_id from epic.jsonl>", "ts": "'$(date -u +%Y-%m-%dT%H:%M:%S.%6N+00:00)'", "event": "tests_approved", "epic": <N>}' >> .planning/epics/E<N>/epic.jsonl
```

3. If plan.json was changed, commit and push:

```bash
git add .planning/epics/E<N>/plan.json .planning/epics/E<N>/epic.jsonl
git commit -m "test(epic-<N>): test specs reviewed and approved"
git pull --rebase && git push
```

4. If only the JSONL was updated (no spec changes):

```bash
git add .planning/epics/E<N>/epic.jsonl
git commit -m "test(epic-<N>): test specs approved"
git pull --rebase && git push
```

### Step 6: Completion

Tell the user:
- Test specs approved and committed
- Next step: `just epic <N>` (generates tests, then executes stories)

---

## Context Sources

| Source | Path | Purpose |
|--------|------|---------|
| Plan | `.planning/epics/E<N>/plan.json` | Stories and test specs |
| JSONL log | `.planning/epics/E<N>/epic.jsonl` | Gate events |
| Fixture catalogue | `tests/FIXTURES.md` | Available test fixtures (read if user asks about fixtures) |

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.
