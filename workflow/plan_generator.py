"""V2 plan generation — single Opus invocation with structured output.

Reads CONTEXT.md (from context assembly), constructs the planner prompt,
dispatches via dispatch_agent() with --json-schema, and parses the output
into plan.json via Pydantic. PLAN.md is rendered deterministically from
the model.

Reference: Research doc Section 8.4 Decisions 1, 3, 4, 5, 6, 7.

Usage:
    python -m workflow.plan_generator <epic_number>
"""

import contextlib
import json
import logging
import re
import sys
from pathlib import Path

from workflow.dispatch import (
    BUDGET_DEFAULTS,
    FALLBACK_MODELS,
    dispatch_with_fallback,
)
from workflow.models import Plan, render_plan_md

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""


# ---------------------------------------------------------------------------
# Context reader
# ---------------------------------------------------------------------------


def _read_context(epic_dir: Path) -> str:
    """Read CONTEXT.md from the epic directory."""
    context_path = epic_dir / "CONTEXT.md"
    if not context_path.is_file():
        raise PlanGenerationError(
            f"CONTEXT.md not found at {context_path}. "
            "Run context assembly first: python -m workflow.context_assembler <number>"
        )
    return context_path.read_text(encoding="utf-8")


def _read_epic_number(epic_dir: Path) -> int:
    """Extract the epic number from the directory name (e.g. E95 -> 95)."""
    match = re.match(r"^E(\d+)$", epic_dir.name)
    if match:
        return int(match.group(1))
    raise PlanGenerationError(f"Cannot extract epic number from directory name: {epic_dir.name}")


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
    epic_number: int,
) -> str:
    """Construct the Opus planner prompt.

    The prompt instructs Opus to produce a plan.json structure only.
    PLAN.md is rendered deterministically from the validated model.
    """
    prompt = f"""\
# Task: Generate Epic Plan

You are the planner for the GTS (Guitar Tone Shootout) project. Your job is to
produce a complete plan for epic #{epic_number} that will be executed by AI agents
under an automated orchestrator.

You must produce a JSON object conforming to the structure enforced by --json-schema.
The orchestrator parses this JSON directly. A separate process renders PLAN.md from
the JSON, so you do NOT produce PLAN.md.

---

## Input Context

The following is the assembled context for this epic, including the epic description
from GitHub and codebase architecture.

<context>
{context}
</context>

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

### Step 6: Specify Wiki Sections

For each story, specify `wiki_sections` — a list of wiki section header names from
the project wiki indexes (`.planning/wiki-indexes/`). The Stage 4 prompt builder
uses this to load targeted wiki sections into each story's agent prompt, keeping
prompt size manageable.

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

## Output

Produce a single JSON object. The structure is enforced by --json-schema.

Key fields:
- `schema_v`: always 1
- `epic_number`: {epic_number}
- `goal`: outcome-shaped goal statement
- `observable_truths`: array of {{id, statement}}
- `user_journeys`: array with journey_id (pattern "J1", "J2", ...), persona,
  narrative, truths_covered, entry_point, critical_transitions
- `stories`: ordered array with story_id (pattern "01-name"), name, purpose,
  agent config, scope, implementation_notes, truths_addressed, wiki_sections
- `validation_checkpoints`: array with after_story, check_type, checks

The `from` field in critical_transitions uses the JSON key "from" (not "from_").

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
11. Every story MUST include `wiki_sections` — a list of wiki section header names
    from `.planning/wiki-indexes/` for the Stage 4 prompt builder.
"""

    return prompt


# ---------------------------------------------------------------------------
# Revision prompts
# ---------------------------------------------------------------------------


def build_revision_prompt(
    original_prompt: str,
    validation_errors: list[str],
) -> str:
    """Build a revision prompt when Phase A validation fails.

    Appends the validation errors to the original prompt so the planner
    can fix structural issues in plan.json.
    """
    error_list = "\n".join(f"- {err}" for err in validation_errors)

    revision_section = f"""

---

## REVISION REQUIRED

Your previous plan.json output failed structural validation. Fix the following
errors and re-emit the plan JSON object:

{error_list}

All other instructions from the original prompt still apply. Produce a single
JSON object conforming to the --json-schema.
"""

    return original_prompt + revision_section


def build_verifier_revision_prompt(
    original_prompt: str,
    verifier_result: dict,
) -> str:
    """Build a revision prompt when Phase B verification fails.

    Appends the structured verifier output so the planner can address
    specific gaps: journey incompleteness, uncovered transitions, intent
    misalignment, logical gaps, and weak validations.
    """
    feedback_lines = [
        "",
        "---",
        "",
        "## REVISION REQUIRED (Verifier Feedback)",
        "",
        "Your plan was structurally valid but failed verification. Address the "
        "following issues and re-emit the plan JSON object:",
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
        "Fix all issues above. Produce a single JSON object conforming to " "the --json-schema."
    )

    return original_prompt + "\n".join(feedback_lines)


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------


def _parse_structured_plan(result) -> Plan:
    """Parse a dispatch result into a validated Plan model.

    Claude Code with --json-schema returns the JSON in the result field
    of the output envelope. The structured_output dict contains the full
    envelope; the output string contains just the result text.

    Args:
        result: AgentResult from dispatch.

    Returns:
        Validated Plan model.

    Raises:
        PlanGenerationError: If output cannot be parsed or validated.
    """
    # Try structured_output first — Claude Code envelope has a "result" key
    # containing the JSON string when --json-schema is used.
    data = None

    if result.structured_output and isinstance(result.structured_output, dict):
        # Check structured_output envelope field first (--json-schema output)
        so_field = result.structured_output.get("structured_output")
        if isinstance(so_field, dict):
            data = so_field
        elif isinstance(so_field, str):
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(so_field)

        # Then check the "result" field
        if data is None:
            result_field = result.structured_output.get("result")
            if isinstance(result_field, str):
                with contextlib.suppress(json.JSONDecodeError):
                    data = json.loads(result_field)
            elif isinstance(result_field, dict):
                data = result_field

    # Fallback: try parsing the output text directly
    if data is None and result.output:
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(result.output)

    if data is None:
        raise PlanGenerationError(
            "Could not extract JSON from planner output. "
            f"Output (first 500 chars): {result.output[:500]}"
        )

    try:
        return Plan.model_validate(data)
    except Exception as exc:
        raise PlanGenerationError(f"Plan JSON failed Pydantic validation: {exc}") from exc


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def generate_plan(
    epic_dir: Path,
) -> tuple[Path, Path]:
    """Generate PLAN.md and plan.json from assembled context.

    Dispatches a single Opus invocation with --json-schema and tools=[]
    to get structured plan output. PLAN.md is rendered deterministically
    from the validated Pydantic model.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain CONTEXT.md from context assembly.

    Returns:
        Tuple of (plan_md_path, plan_json_path).

    Raises:
        PlanGenerationError: If context is missing, dispatch fails, or
            output cannot be parsed.
    """
    # Read inputs
    context = _read_context(epic_dir)
    epic_number = _read_epic_number(epic_dir)

    # Build the planner prompt
    prompt = _build_planner_prompt(
        context=context,
        epic_number=epic_number,
    )

    logger.info(
        "Dispatching Opus planner for epic #%d (%d chars, ~%d tokens)",
        epic_number,
        len(prompt),
        len(prompt) // 4,
    )

    # Generate JSON Schema from Pydantic model
    plan_schema = Plan.model_json_schema()

    # Dispatch with tools=[] and json_schema for structured output.
    # No tools needed — all context is in the prompt.
    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=[],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        json_schema=plan_schema,
        cwd=PROJECT_ROOT,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Opus planner dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    logger.info(
        "Planner output length: %d chars, turns: %s",
        len(result.output),
        result.turns or "unknown",
    )

    # Parse structured output into Pydantic model
    plan = _parse_structured_plan(result)

    # Write plan.json (serialised from validated model)
    plan_json_path = epic_dir / "plan.json"
    plan_json_path.write_text(
        json.dumps(plan.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote plan.json to %s", plan_json_path)

    # Render and write PLAN.md deterministically
    plan_md_path = epic_dir / "PLAN.md"
    plan_md_path.write_text(render_plan_md(plan), encoding="utf-8")
    logger.info("Wrote PLAN.md to %s", plan_md_path)

    return plan_md_path, plan_json_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python -m workflow.plan_generator <epic_number>."""
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <epic_number>",
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
        plan_md_path, plan_json_path = generate_plan(epic_dir)
        print(f"Plan generated for epic #{epic_number}:")
        print(f"  PLAN.md:   {plan_md_path.relative_to(PROJECT_ROOT)}")
        print(f"  plan.json: {plan_json_path.relative_to(PROJECT_ROOT)}")
    except PlanGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
