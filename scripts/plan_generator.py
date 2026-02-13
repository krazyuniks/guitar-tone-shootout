"""V2 plan generation — single Opus invocation.

Reads CONTEXT.md (from Step 6), appends locked scope decisions, constructs
the planner prompt, dispatches via dispatch_agent(), and parses the output
into PLAN.md and plan.json.  This single Opus invocation replaces the V1
pipeline of 3 separate AI invocations (context-loader, gray-area-analyst,
goal-backward + task-breakdown).

Reference: Research doc Section 8.4 Decisions 1, 3, 4, 5, 6, 7.

Usage:
    python scripts/plan_generator.py <epic_number> [--decisions decisions.json]
"""

import json
import logging
import re
import sys
from pathlib import Path

from scripts.dispatch import (
    BUDGET_DEFAULTS,
    FALLBACK_MODELS,
    dispatch_with_fallback,
    get_tools_for_role,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
SCHEMAS_DIR = PROJECT_ROOT / "scripts" / "schemas"

logger = logging.getLogger(__name__)


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""


# ---------------------------------------------------------------------------
# Plan schema loader
# ---------------------------------------------------------------------------


def _load_plan_schema() -> dict:
    """Load the plan.json JSON Schema for inclusion in the planner prompt."""
    schema_path = SCHEMAS_DIR / "plan.schema.json"
    if not schema_path.is_file():
        raise PlanGenerationError(
            f"Plan schema not found at {schema_path}. " "Ensure Step 1 schemas are in place."
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Context reader
# ---------------------------------------------------------------------------


def _read_context(epic_dir: Path) -> str:
    """Read CONTEXT.md from the epic directory."""
    context_path = epic_dir / "CONTEXT.md"
    if not context_path.is_file():
        raise PlanGenerationError(
            f"CONTEXT.md not found at {context_path}. "
            "Run context assembly first: python scripts/context_assembler.py <number>"
        )
    return context_path.read_text(encoding="utf-8")


def _read_epic_number(epic_dir: Path) -> int:
    """Extract the epic number from the directory name (e.g. E95 -> 95)."""
    match = re.match(r"^E(\d+)$", epic_dir.name)
    if match:
        return int(match.group(1))
    raise PlanGenerationError(f"Cannot extract epic number from directory name: {epic_dir.name}")


# ---------------------------------------------------------------------------
# Decision formatting
# ---------------------------------------------------------------------------


def _format_decisions(decisions: dict) -> str:
    """Format locked scope decisions for injection into the planner prompt.

    Decisions are a dict of question -> answer pairs from the interactive
    Phase 2 scope discussion.  They are appended to the context so the
    planner can incorporate them.
    """
    if not decisions:
        return ""

    lines = [
        "## Locked Scope Decisions",
        "",
        "The following decisions were confirmed during the interactive scope discussion. "
        "Treat them as hard constraints when generating the plan.",
        "",
    ]
    for question, answer in decisions.items():
        lines.append(f"**Q:** {question}")
        lines.append(f"**A:** {answer}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planner prompt construction
# ---------------------------------------------------------------------------

# Evidence fields per check type (Section 8.4 Decision 4)
EVIDENCE_FIELDS_TABLE = """\
| Check Type | Required Evidence Fields |
|------------|------------------------|
| `http` | `status_code`, `url`, `response_excerpt` |
| `http+dom` | `status_code`, `url`, `dom_selector`, `element_text` |
| `browser+db` | `action_performed`, `sql_query`, `row_count`, `sample_row` |
| `api+response` | `status_code`, `url`, `method`, `response_body_excerpt` |
| `process` | `process_name`, `pid_or_status`, `log_excerpt` |
| `screenshot` | `screenshot_path`, `observations` |
| `regression` | `test_command`, `exit_code`, `test_count`, `failure_count` |
| `quality` | `commands_run`, `exit_code`, `error_count` |"""

# Checkpoint placement guidance (Section 8.4 Decision 5)
CHECKPOINT_PLACEMENT_GUIDANCE = """\
Place validation checkpoints strategically based on story types:
- After scaffolding: pages exist, routes respond, navigation works.
- After CRUD: create/read/update/delete work end-to-end.
- After complex features: feature-specific behaviour verified.
- Before regression tests: full product works (don't waste tokens testing broken product).
- After regression tests: tests pass, quality gates pass (final gate).

Not every story needs a checkpoint. Backend-only stories (entity + repo + service)
may wait for the UI story that exposes them. The key is to catch wiring failures
before building on top of broken scaffolding."""

# Story sizing guidance (Section 8.4 Decision 7)
STORY_SIZING_GUIDANCE = """\
Story sizing constraints:
- Target 2-5 stories per epic. Each story is a coherent chunk an agent completes
  in one invocation.
- 3-8 files created/modified per story.
- Each story should use <50% of the agent context window.
- Full vertical slice OR one layer across multiple entities.
- Each story should produce something checkable.
- Each story builds on the previous but is self-contained.
- State assumption: declare whether the story expects cumulative state (default)
  or clean state (orchestrator runs db-reset before dispatch).

Example story breakdown for a typical GTS epic:
| Story | Scope | Model | Budget |
|-------|-------|-------|--------|
| 1. Architecture | Entity, ORM, repo, service, migration | Sonnet | $3 |
| 2. API + Schemas | Routes, Pydantic schemas, route registration | Sonnet | $2 |
| 3. UI Scaffolding | Page templates, fragments, navigation | Sonnet | $3 |
| 4. CRUD Features | Form handling, HTMX interactions, DB writes | Sonnet | $4 |
| 5. Regression Tests | E2E tests, regression test updates | Sonnet | $3 |"""

# Skill mapping per story type (Section 8.5 Decision 3)
SKILL_MAPPING_REFERENCE = """\
Skill mapping per story type (select appropriate skills for each story):
| Story Type | Typical Skills |
|------------|---------------|
| Architecture | `gts-architecture`, `repository-patterns`, `service-patterns` |
| API + Schemas | `gts-backend-dev`, `web-handlers`, `error-handling` |
| UI Scaffolding | `gts-frontend-dev`, `htmx`, `astro-frontend` |
| CRUD Features | `gts-frontend-dev`, `htmx`, `gts-backend-dev` |
| Regression Tests | `gts-testing`, `playwright` |"""

# Tool restrictions per agent role (Section 8.2 Strategy 4)
TOOL_REFERENCE = """\
Tool restrictions per agent role:
| Agent Role | Tools |
|------------|-------|
| Implementation | Read, Edit, Write, Bash, Glob, Grep |
| Validation (browser) | Read, Bash, Glob, Grep + MCP |
| Validation (API/DB) | Bash, Read, Glob, Grep |
| Regression test | Read, Edit, Write, Bash, Glob, Grep |"""

# Budget defaults (Section 8.2 Strategy 7)
BUDGET_REFERENCE = """\
Budget defaults (starting points):
| Agent Type | Max Turns | Max Budget |
|------------|-----------|------------|
| Architecture (Sonnet) | 30 | $3.00 |
| Implementation (Sonnet) | 40 | $4.00 |
| Validation (Haiku) | 15 | $0.50 |
| Regression tests (Sonnet) | 30 | $3.00 |"""


def _build_planner_prompt(
    context: str,
    decisions_text: str,
    plan_schema: dict,
    epic_number: int,
) -> str:
    """Construct the Opus planner prompt.

    The prompt instructs Opus to:
    1. Perform goal-backward analysis (truths -> artefacts -> stories)
    2. Produce user journeys with critical_transitions
    3. Write PLAN.md in narrative structure
    4. Emit plan.json conforming to the JSON Schema
    5. Specify full agent config per story
    6. Include state_assumption per story
    7. Place validation checkpoints strategically
    """
    schema_json = json.dumps(plan_schema, indent=2)

    prompt = f"""\
# Task: Generate Epic Plan

You are the planner for the GTS (Guitar Tone Shootout) project. Your job is to
produce a complete plan for epic #{epic_number} that will be executed by AI agents
under an automated orchestrator.

You must produce TWO outputs:
1. **PLAN.md** — a human-readable narrative plan (for review at the Decision Gate)
2. **plan.json** — a machine-readable plan conforming to the JSON Schema below

Both must contain the same information. The orchestrator parses ONLY plan.json.
PLAN.md is for human reviewers.

---

## Input Context

The following is the assembled context for this epic, including the epic description
from GitHub, codebase architecture, detected architecture areas, and locked scope
decisions.

<context>
{context}
</context>

{decisions_text}

---

## Planning Methodology: Goal-Backward Analysis

Follow this methodology strictly:

### Step 1: Define Observable Truths

Define observable truths — user-perspective, verifiable-by-a-human statements that
define "done". These are NOT technical requirements. They describe what a user can
see or do when the epic is complete.

Good truths:
- "A user can visit /gear and see a list of their gear items"
- "Clicking a gear item navigates to a detail page showing model information"
- "Submitting the edit form updates the gear name, visible on return to detail page"

Bad truths (too technical):
- "GearRepository has a get_by_id method"
- "The Pydantic schema validates input"
- "The migration adds a gear table"

### Step 2: Derive Required Artefacts

For each truth, identify what code artefacts must exist for the truth to be
observable. Walk the full stack: entity -> ORM model -> repository -> service ->
API endpoint -> page template -> navigation link.

### Step 3: Organise Artefacts into Stories

Group artefacts into stories. Each story is a coherent chunk that one AI agent
completes in a single invocation.

{STORY_SIZING_GUIDANCE}

### Step 4: Define User Journeys

Create connected, end-to-end narratives that link observable truths into coherent
flows. Not isolated assertions ("GET /gear returns 200") but connected walks
("user clicks Gear in nav, sees list, clicks item, sees detail").

Every truth must appear in at least one journey. Journeys include
critical_transitions with {{from, to, mechanism}}.

### Step 5: Place Validation Checkpoints

{CHECKPOINT_PLACEMENT_GUIDANCE}

---

## Agent Configuration Reference

For each story, specify the full agent dispatch configuration.

{SKILL_MAPPING_REFERENCE}

{TOOL_REFERENCE}

{BUDGET_REFERENCE}

MCP servers (specify in the `mcp` array):
- `chrome-devtools` — for stories that need browser DOM inspection
- `playwright` — for stories that need browser automation (E2E tests)
- Most stories need NO MCP (empty array `[]`)

---

## Evidence Fields per Check Type

Each validation checkpoint must specify `evidence_fields` per criterion. Use the
correct fields for the check type:

{EVIDENCE_FIELDS_TABLE}

---

## Output Format

### Output 1: PLAN.md

Write the plan in this exact structure:

```
# Plan: {{Epic Title}}

## Goal

{{Outcome-shaped goal statement from goal-backward analysis}}

## Observable Truths

1. {{Truth 1 — user perspective, verifiable by a human}}
2. {{Truth 2}}
...

## User Journeys

### Journey 1: {{Persona}} — {{Summary}}

{{Narrative: connected end-to-end walkthrough in plain English, present tense.
Covers happy path from entry point through all critical transitions.}}

**Truths covered:** 1, 2, 3
**Entry point:** /path
**Critical transitions:**
- {{from}} -> {{to}} ({{mechanism}})

## Stories

### Story 1: {{Name}}

**Purpose:** {{What this story delivers — 1-2 sentences}}

**Agent:**
- model: {{sonnet|opus|haiku}}
- skills: [{{skill1}}, {{skill2}}]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: {{[] or [chrome-devtools] or [playwright]}}
- max_turns: {{number}}
- max_budget_usd: {{number}}

**Scope:**
- Create: `{{path/to/new/file.py}}`
- Modify: `{{path/to/existing/file.py}}`

**Implementation Notes:**
- {{Domain-specific hint}}

**Truths Addressed:** {{1, 2}}

---

### Validation Checkpoint: After {{Story Name}}

**Type:** {{check_type}}
**Checks:**
- {{criterion}} (evidence: {{field1}}, {{field2}})

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| Truth 1 | {{artefacts}} | Story 1 |
```

### Output 2: plan.json

Emit a valid JSON object conforming to this schema. The schema is a HARD CONSTRAINT.
Every required field must be present with the correct type.

<schema>
{schema_json}
</schema>

---

## Output Delimiters

Emit the two outputs separated by these exact delimiters:

```
===PLAN_MD_START===
(PLAN.md content here)
===PLAN_MD_END===

===PLAN_JSON_START===
(plan.json content here — valid JSON, no markdown fences)
===PLAN_JSON_END===
```

---

## Critical Rules

1. Every observable truth must be addressed by at least one story.
2. Every observable truth must appear in at least one journey's truths_covered.
3. Every checkpoint after_story must reference a valid story_id.
4. Every journey truths_covered ID must exist in observable_truths.
5. Files in scope.modify must be real files that exist in the GTS codebase.
6. Files in scope.create must have parent directories that exist.
7. Stories that use files created by earlier stories must appear after them.
8. state_assumption defaults to "cumulative". Only set "clean" when validation
   criteria depend on known data state.
9. The plan.json epic_number must be {epic_number}.
10. Do NOT invent features not described in the epic. Stay within scope.
"""

    return prompt


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------


def _extract_delimited(output: str, start_marker: str, end_marker: str) -> str | None:
    """Extract content between two delimiter markers."""
    start_idx = output.find(start_marker)
    if start_idx == -1:
        return None
    start_idx += len(start_marker)
    end_idx = output.find(end_marker, start_idx)
    if end_idx == -1:
        return None
    return output[start_idx:end_idx].strip()


def _parse_plan_output(output: str) -> tuple[str, dict]:
    """Parse the planner's output into PLAN.md content and plan.json dict.

    The planner is instructed to emit output with delimiters:
    ===PLAN_MD_START=== ... ===PLAN_MD_END===
    ===PLAN_JSON_START=== ... ===PLAN_JSON_END===

    If delimiters are missing, fall back to heuristic extraction.

    Returns:
        Tuple of (plan_md_content, plan_json_dict).

    Raises:
        PlanGenerationError: If output cannot be parsed.
    """
    # Try delimiter-based extraction first
    plan_md = _extract_delimited(output, "===PLAN_MD_START===", "===PLAN_MD_END===")
    plan_json_str = _extract_delimited(output, "===PLAN_JSON_START===", "===PLAN_JSON_END===")

    # If delimiters worked, parse the JSON
    if plan_md and plan_json_str:
        try:
            plan_json = json.loads(plan_json_str)
            return plan_md, plan_json
        except json.JSONDecodeError as exc:
            raise PlanGenerationError(
                f"plan.json content between delimiters is not valid JSON: {exc}"
            ) from exc

    # Fallback: try to find JSON block in the output
    # Look for the largest JSON object in the output
    plan_json = _extract_json_fallback(output)
    if plan_json is None:
        raise PlanGenerationError(
            "Could not extract plan.json from planner output. "
            "Expected ===PLAN_JSON_START=== / ===PLAN_JSON_END=== delimiters "
            "or a JSON object containing 'schema_v' and 'stories'."
        )

    # For PLAN.md, if delimiters missing, use everything before the JSON block
    if plan_md is None:
        plan_md = _extract_plan_md_fallback(output)

    return plan_md, plan_json


def _extract_json_fallback(output: str) -> dict | None:
    """Attempt to extract a plan.json object from unstructured output.

    Searches for JSON objects that contain the expected plan fields
    (schema_v, stories). Returns the first valid match.
    """
    # Find all potential JSON objects (starting with { at various positions)
    # Try progressively from the end (the JSON is likely emitted last)
    candidates = []
    for match in re.finditer(r"\{", output):
        start = match.start()
        # Try to find the matching closing brace by attempting JSON parse
        # Starting from longer substrings
        depth = 0
        for i in range(start, len(output)):
            if output[i] == "{":
                depth += 1
            elif output[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = output[start : i + 1]
                    candidates.append(candidate)
                    break

    # Try each candidate, preferring ones with plan-specific fields
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "stories" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue

    return None


def _extract_plan_md_fallback(output: str) -> str:
    """Extract PLAN.md content from unstructured output as a fallback.

    Looks for markdown content that starts with a heading like "# Plan:".
    If not found, returns the full output (better than nothing).
    """
    # Look for the plan heading
    match = re.search(r"(# Plan:.*)", output, re.DOTALL)
    if match:
        plan_text = match.group(1)
        # Trim at the JSON block if present
        json_start = plan_text.find('{"schema_v"')
        if json_start > 0:
            plan_text = plan_text[:json_start].strip()
        return plan_text

    return output


# ---------------------------------------------------------------------------
# Revision prompt for Phase A failures
# ---------------------------------------------------------------------------


def build_revision_prompt(
    original_prompt: str,
    validation_errors: list[str],
) -> str:
    """Build a revision prompt when Phase A validation fails.

    Appends the validation errors to the original prompt so the planner
    can fix structural issues in plan.json.

    Args:
        original_prompt: The original planner prompt.
        validation_errors: List of specific validation error messages.

    Returns:
        Revised prompt with error context.
    """
    error_list = "\n".join(f"- {err}" for err in validation_errors)

    revision_section = f"""

---

## REVISION REQUIRED

Your previous plan.json output failed structural validation. Fix the following
errors and re-emit both PLAN.md and plan.json:

{error_list}

All other instructions from the original prompt still apply. Emit the corrected
output using the same delimiters (===PLAN_MD_START=== etc.).
"""

    return original_prompt + revision_section


# ---------------------------------------------------------------------------
# Verifier feedback revision prompt
# ---------------------------------------------------------------------------


def build_verifier_revision_prompt(
    original_prompt: str,
    verifier_result: dict,
) -> str:
    """Build a revision prompt when Phase B verification fails.

    Appends the structured verifier output so the planner can address
    specific gaps: journey incompleteness, uncovered transitions, intent
    misalignment, logical gaps, and weak validations.

    Args:
        original_prompt: The original planner prompt.
        verifier_result: Structured output from the plan verifier.

    Returns:
        Revised prompt with verifier feedback.
    """
    feedback_lines = [
        "",
        "---",
        "",
        "## REVISION REQUIRED (Verifier Feedback)",
        "",
        "Your plan was structurally valid but failed verification. Address the "
        "following issues and re-emit both PLAN.md and plan.json:",
        "",
    ]

    # Journey completeness
    jc = verifier_result.get("journey_completeness", {})
    if jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in jc.get("gaps", []):
            feedback_lines.append(
                f"- Journey {gap.get('journey_id', '?')}: "
                f"step '{gap.get('step', '?')}' — {gap.get('missing', '?')}"
            )
        feedback_lines.append("")

    # Transition coverage
    tc = verifier_result.get("transition_coverage", {})
    if tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in tc.get("uncovered", []):
            feedback_lines.append(
                f"- Journey {uc.get('journey_id', '?')}: "
                f"{uc.get('from', '?')} -> {uc.get('to', '?')} "
                f"({uc.get('mechanism', '?')})"
            )
        feedback_lines.append("")

    # Intent alignment
    ia = verifier_result.get("intent_alignment", {})
    if ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in ia.get("unaddressed_requirements", []):
            feedback_lines.append(f"- Unaddressed requirement: {req}")
        for creep in ia.get("scope_creep", []):
            feedback_lines.append(f"- Scope creep: {creep}")
        feedback_lines.append("")

    # Gap detection
    gd = verifier_result.get("gap_detection", {})
    if gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in gd.get("gaps", []):
            between = gap.get("between", [])
            between_str = " and ".join(between) if between else "?"
            feedback_lines.append(f"- Between {between_str}: {gap.get('missing', '?')}")
        feedback_lines.append("")

    # Validation sufficiency
    vs = verifier_result.get("validation_sufficiency", {})
    if vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in vs.get("weak_checks", []):
            feedback_lines.append(
                f"- Checkpoint '{wc.get('checkpoint', '?')}', "
                f"criterion '{wc.get('criterion', '?')}': {wc.get('risk', '?')}"
            )
        feedback_lines.append("")

    feedback_lines.append(
        "Fix all issues above. Emit corrected output using the same delimiters "
        "(===PLAN_MD_START=== etc.)."
    )

    return original_prompt + "\n".join(feedback_lines)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def generate_plan(
    epic_dir: Path,
    decisions: dict | None = None,
) -> tuple[Path, Path]:
    """Generate PLAN.md and plan.json from assembled context.

    This is the single Opus AI invocation that replaces 3 AI invocations
    in V1 (context-loader, goal-backward, task-breakdown).

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain CONTEXT.md from Step 6.
        decisions: Locked scope decisions from the interactive Phase 2
            discussion. Dict of question -> answer pairs. May be None
            if no interactive decisions were made.

    Returns:
        Tuple of (plan_md_path, plan_json_path).

    Raises:
        PlanGenerationError: If context is missing, dispatch fails, or
            output cannot be parsed.
    """
    if decisions is None:
        decisions = {}

    # Read inputs
    context = _read_context(epic_dir)
    epic_number = _read_epic_number(epic_dir)
    plan_schema = _load_plan_schema()

    # Format decisions
    decisions_text = _format_decisions(decisions)

    # Build the planner prompt
    prompt = _build_planner_prompt(
        context=context,
        decisions_text=decisions_text,
        plan_schema=plan_schema,
        epic_number=epic_number,
    )

    logger.info(
        "Dispatching Opus planner for epic #%d (%d chars, ~%d tokens)",
        epic_number,
        len(prompt),
        len(prompt) // 4,
    )

    # Dispatch via Opus with Sonnet fallback
    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=get_tools_for_role("implementation"),
        skills=["gts-architecture", "gts-backend-dev", "gts-frontend-dev"],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        cwd=PROJECT_ROOT,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Opus planner dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    # Extract the output text
    output = result.output
    if result.structured_output and isinstance(result.structured_output, dict):
        # Claude --output-format json wraps the result; extract the text
        text_output = result.structured_output.get("result", "")
        if text_output:
            output = text_output

    # Parse the planner's output
    plan_md_content, plan_json_dict = _parse_plan_output(output)

    # Write PLAN.md
    plan_md_path = epic_dir / "PLAN.md"
    plan_md_path.write_text(plan_md_content, encoding="utf-8")
    logger.info("Wrote PLAN.md to %s", plan_md_path)

    # Write plan.json
    plan_json_path = epic_dir / "plan.json"
    plan_json_path.write_text(
        json.dumps(plan_json_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote plan.json to %s", plan_json_path)

    return plan_md_path, plan_json_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python scripts/plan_generator.py <epic_number> [--decisions file.json]."""
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <epic_number> [--decisions decisions.json]",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(
            f"Error: epic_number must be an integer, got: {sys.argv[1]}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse optional --decisions flag
    decisions: dict = {}
    if "--decisions" in sys.argv:
        idx = sys.argv.index("--decisions")
        if idx + 1 >= len(sys.argv):
            print("Error: --decisions requires a file path argument", file=sys.stderr)
            sys.exit(1)
        decisions_path = Path(sys.argv[idx + 1])
        if not decisions_path.is_file():
            print(f"Error: decisions file not found: {decisions_path}", file=sys.stderr)
            sys.exit(1)
        try:
            decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON in decisions file: {exc}", file=sys.stderr)
            sys.exit(1)

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(
            f"Error: Epic directory not found: {epic_dir}. "
            f"Run ingestion and context assembly first.",
            file=sys.stderr,
        )
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        plan_md_path, plan_json_path = generate_plan(epic_dir, decisions)
        print(f"Plan generated for epic #{epic_number}:")
        print(f"  PLAN.md:   {plan_md_path.relative_to(PROJECT_ROOT)}")
        print(f"  plan.json: {plan_json_path.relative_to(PROJECT_ROOT)}")
    except PlanGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
