"""Plan generation — agent-based planner producing JSON.

The planner receives only the enriched epic body (from GitHub) and the
plan.json schema. It explores the codebase itself using tools (Read, Grep,
Glob) rather than receiving pre-assembled context.

Dispatches via dispatch_agent(), parses the output into plan.json via
Pydantic. PLAN.md is rendered deterministically from the model.

Usage:
    python -m workflow.plan_generator <epic_number>
"""

import json
import logging
import re
import sys
from pathlib import Path

from workflow.dispatch import (
    dispatch_agent,
    get_dispatch_params,
)
from workflow.epic_config import EpicConfig
from workflow.models import Plan, render_plan_md

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""


# ---------------------------------------------------------------------------
# Input readers
# ---------------------------------------------------------------------------


def _read_epic_md(epic_dir: Path) -> str:
    """Read EPIC.md from the epic directory."""
    epic_path = epic_dir / "EPIC.md"
    if not epic_path.is_file():
        raise PlanGenerationError(
            f"EPIC.md not found at {epic_path}. "
            "Run ingestion first: ./wf epic run <number>"
        )
    return epic_path.read_text(encoding="utf-8")


def _read_epic_number(epic_dir: Path) -> int:
    """Extract the epic number from the directory name (e.g. E95 -> 95)."""
    match = re.match(r"^E(\d+)$", epic_dir.name)
    if match:
        return int(match.group(1))
    raise PlanGenerationError(f"Cannot extract epic number from directory name: {epic_dir.name}")


# ---------------------------------------------------------------------------
# Planner prompt construction
# ---------------------------------------------------------------------------

CHECKPOINT_PLACEMENT_GUIDANCE = """\
Place validation checkpoints strategically based on story types:
- After scaffolding: pages exist, routes respond, navigation works.
- After CRUD: create/read/update/delete work end-to-end.
- After complex features: feature-specific behaviour verified.
- Before regression tests: full product works (don't waste tokens testing broken product).
- After regression tests: tests pass, quality gates pass (final gate).

Not every story needs a checkpoint. Backend-only stories (entity + repo + service)
may wait for the UI story that exposes them. The key is to catch wiring failures
before building on top of broken scaffolding.

Use explicit `command` values whenever the check maps cleanly to a `just`
recipe or `just tdd <path> -k <test>`. Weak checks like bare 200s, greps, or
"button exists" checks are not enough when the epic requires a real journey."""


def _build_planner_prompt(
    epic_md: str,
    epic_number: int,
) -> str:
    """Construct the planner prompt.

    The planner is a tool-equipped agent. It receives only the epic body
    and JSON schema, and explores the codebase using tools (Read, Grep,
    Glob) to find actual files, services, models, and routes.

    PLAN.md is rendered deterministically from the validated model.
    """
    prompt = f"""\
# Task: Generate Epic Plan

Produce a complete `plan.json` for epic #{epic_number}. You are a tool-equipped
planner: inspect the repo live, find the real files and routes, and build a
plan that matches the epic contract exactly.

Read AGENTS.md and DEVELOPMENT.md first for project conventions and structure.

Output only a single JSON object matching the provided schema. Do not produce
markdown, commentary, or `PLAN.md`. Use the StructuredOutput tool for the
final answer.

## Epic Contract

<epic>
{epic_md}
</epic>

Before emitting the JSON, verify your own work:
- Count your observable truths and confirm every ID appears in at least one
  story's truths_addressed AND at least one journey's truths_covered.
- Confirm every checkpoint after_story references a real story_id.
- Confirm every scope.modify path points to a file that actually exists (use
  Glob to verify).
- For every user journey, verify the entry point and source page/state either
  exist today or are explicitly created/fixed in story scope.
- For every critical transition, verify the plan proves all 3 parts:
  source page/state renders, transition mechanism works, target page/state
  renders after the transition.
- Reconcile every route/path named in the epic against the actual repo. If the
  current code or tests expect a 404/different path, plan the source-page fix
  explicitly instead of assuming the journey already works.
- For every UI -> API interaction, define one end-to-end transport contract.
  If the UX uses HTMX/Alpine/fetch and the API contract is JSON, spell out the
  exact bridge and add checkpoints that prove it.
- For every redirect or HX-Redirect flow, verify the plan checks both the
  redirect mechanism and the renderability of the destination page.
- If the current codebase suggests a familiar local pattern but the epic
  contract says something else, the epic contract wins.
- List any gaps and fix them before writing the JSON object.

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

Bad truths (too technical):
- "GearRepository has a get_by_id method"
- "The Pydantic schema validates input"

### Step 2: Explore the Codebase

Use your tools to understand the current state:
- Read AGENTS.md and DEVELOPMENT.md for conventions
- Grep for existing patterns (repositories, services, API routes, templates)
- Find files that will need modification
- Understand the module structure and dependency rules

### Step 3: Organise Artefacts into Stories

Group artefacts into stories. Each story is a coherent chunk that one AI agent
completes in a single invocation.

Story sizing constraints:
- ONE FEATURE PER STORY. Never bundle unrelated features into one story.
- Each story is a vertical slice: one feature through all layers.
- 3-8 files created/modified per story.
- Each story should produce something checkable.
- Each story builds on the previous but is self-contained.
- More stories is fine. Prefer 5 focused stories over 3 bloated ones.
- state_assumption defaults to "cumulative". Only set "clean" when validation
  criteria depend on known data state.

### Step 3b: Enrich Each Story

For EVERY story, populate these fields with specific, concrete information:

- **acceptance_criteria**: User-perspective, testable statements. Each must be
  independently verifiable.
- **architectural_context**: Patterns, module boundaries, design decisions.
  Reference actual files so the agent knows where to look.
- **navigation_hints**: File paths, symbol names, entry points. Assume the
  agent starts cold with no knowledge of where things live.
- **implementation_notes**: Domain-specific hints.
- **test_spec**: Optional. If you include it, keep it focused on business
  behaviour to verify after implementation, not on frozen test-first scaffolding.

### Step 4: Define User Journeys

Create connected, end-to-end narratives that link observable truths into coherent
flows. Every truth must appear in at least one journey.

When you define a journey:
- Do NOT invent entry points or source pages without tool evidence.
- If the epic references a source page/link path that is currently missing or
  broken, add scope to build or repair that source state.
- Keep route/path names consistent across the epic, journeys, stories, and
  checkpoints. Resolve ambiguities with repo evidence before emitting JSON.

### Step 5: Place Validation Checkpoints

{CHECKPOINT_PLACEMENT_GUIDANCE}

A transition is only covered when the checkpoint(s) prove:
- the source page/state renders with the expected control,
- the transition mechanism works (click, submit, PATCH, redirect),
- the target page/state renders correctly afterward.

If a story changes an API contract that the frontend consumes, checkpoints must
also prove the transport/wiring end to end, not just the raw endpoint response.

---

## Output

Return one complete JSON object for epic #{epic_number}.

---

## Critical Rules

1. Every observable truth must be addressed by at least one story.
2. Every observable truth must appear in at least one journey's truths_covered.
3. Every checkpoint after_story must reference a valid story_id.
4. Every journey truths_covered ID must exist in observable_truths.
5. Files in scope.modify must be real files that exist in the GTS codebase.
   USE GLOB TO VERIFY.
6. Files in scope.create must have parent directories that exist.
7. Stories that use files created by earlier stories must appear after them.
8. state_assumption defaults to "cumulative". Only set "clean" when validation
   criteria depend on known data state.
9. The plan.json epic_number must be {epic_number}.
10. Do NOT invent features not described in the epic. Stay within scope.
11. Every story MUST have non-empty acceptance_criteria.
12. Every story SHOULD include a test_spec with test_type, fixtures, and assertions.

Think through the repo state carefully, then emit the JSON object."""

    return prompt


# ---------------------------------------------------------------------------
# Revision prompts (legacy — kept for backward compatibility)
# ---------------------------------------------------------------------------


def build_revision_prompt(
    original_prompt: str,
    validation_errors: list[str],
) -> str:
    """Build a revision prompt when Phase A validation fails.

    **Legacy:** No longer called from the revision dispatch path. The
    targeted ``build_targeted_phase_a_revision_prompt`` is used instead.
    """
    error_list = "\n".join(f"- {err}" for err in validation_errors)

    revision_section = f"""

---

## REVISION REQUIRED

Your previous plan.json output failed structural validation. Fix the following
errors and re-emit the plan JSON object:

{error_list}

All other instructions from the original prompt still apply. Produce a single
JSON object and NOTHING ELSE — no markdown, no explanation. Raw JSON only.
"""

    return original_prompt + revision_section


# ---------------------------------------------------------------------------
# Finding extraction helpers (used by both legacy and targeted prompts)
# ---------------------------------------------------------------------------


def _extract_finding_items(dim_data: dict, key: str) -> list:
    """Get finding items from nested dict, flat dict, or array layout."""
    findings = dim_data.get("findings")
    if isinstance(findings, list):
        return [f for f in findings if f.get("severity") == "must_fix"]
    if isinstance(findings, dict):
        items = findings.get(key, [])
        if items:
            return items
    return dim_data.get(key, [])


def _format_finding_item(item: object) -> str:
    """Format a finding item, handling both str and dict."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def build_verifier_revision_prompt(
    original_prompt: str,
    verifier_result: dict,
) -> str:
    """Build a revision prompt when Phase B verification fails.

    **Legacy:** No longer called from the revision dispatch path. The
    targeted ``build_targeted_phase_b_revision_prompt`` is used instead.
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

    dims = verifier_result.get("dimensions")
    if not isinstance(dims, dict):
        dims = verifier_result

    jc = dims.get("journey_completeness", {})
    if isinstance(jc, dict) and jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in _extract_finding_items(jc, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    tc = dims.get("transition_coverage", {})
    if isinstance(tc, dict) and tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in _extract_finding_items(tc, "uncovered"):
            feedback_lines.append(f"- {_format_finding_item(uc)}")
        feedback_lines.append("")

    ia = dims.get("intent_alignment", {})
    if isinstance(ia, dict) and ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in _extract_finding_items(ia, "unaddressed_requirements"):
            feedback_lines.append(f"- Unaddressed requirement: {_format_finding_item(req)}")
        for creep in _extract_finding_items(ia, "scope_creep"):
            feedback_lines.append(f"- Scope creep: {_format_finding_item(creep)}")
        feedback_lines.append("")

    gd = dims.get("gap_detection", {})
    if isinstance(gd, dict) and gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in _extract_finding_items(gd, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    vs = dims.get("validation_sufficiency", {})
    if isinstance(vs, dict) and vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in _extract_finding_items(vs, "weak_checks"):
            feedback_lines.append(f"- {_format_finding_item(wc)}")
        feedback_lines.append("")

    gs = dims.get("gap_sufficiency", {})
    if isinstance(gs, dict) and gs.get("status") == "fail":
        feedback_lines.append("### Missed Gaps")
        for mg in _extract_finding_items(gs, "missed_gaps"):
            feedback_lines.append(f"- {_format_finding_item(mg)}")
        feedback_lines.append("")

    feedback_lines.append(
        "Fix all issues above. Produce a single JSON object conforming to "
        "the schema. Output ONLY the raw JSON, no other text."
    )

    return original_prompt + "\n".join(feedback_lines)


# ---------------------------------------------------------------------------
# Targeted revision prompts (send plan.json + feedback, not full context)
# ---------------------------------------------------------------------------


def build_targeted_phase_a_revision_prompt(
    plan_json_str: str,
    errors: list[str],
) -> str:
    """Build a targeted Phase A revision prompt.

    Sends only the current plan.json + errors + JSON schema (~25K total)
    instead of rebuilding the entire planning prompt.
    """
    error_list = "\n".join(f"- {err}" for err in errors)

    return f"""\
# Task: Fix Plan Validation Errors (Targeted Revision)

The current plan.json failed Phase A structural validation. Fix ONLY the
listed errors. Preserve all other fields exactly as they are.

## Rules

1. Make the MINIMUM changes necessary to fix each error.
2. Do NOT rewrite stories, journeys, or scope unless an error specifically
   requires it.
3. Keep `scope.modify` paths pointing to files that exist on disk RIGHT NOW.
   Use the Glob and Read tools to verify file paths if unsure.
4. Do NOT add new stories or remove existing ones unless an error requires it.
5. Output only the complete JSON object matching the provided schema.
6. Use the StructuredOutput tool for the final answer.

---

## Current Plan

<current_plan>
{plan_json_str}
</current_plan>

---

## Validation Errors to Fix

{error_list}

---

Fix the errors above and emit the complete JSON object.
Do NOT omit any existing fields — the output must be a complete, valid plan."""


def build_targeted_phase_b_revision_prompt(
    epic_md: str,
    plan_json_str: str,
    verifier_result: dict,
) -> str:
    """Build a targeted Phase B revision prompt.

    Sends the original epic contract + current plan.json + must_fix findings.
    """
    feedback_lines: list[str] = []

    dims = verifier_result.get("dimensions")
    if not isinstance(dims, dict):
        dims = verifier_result

    jc = dims.get("journey_completeness", {})
    if isinstance(jc, dict) and jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in _extract_finding_items(jc, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    tc = dims.get("transition_coverage", {})
    if isinstance(tc, dict) and tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in _extract_finding_items(tc, "uncovered"):
            feedback_lines.append(f"- {_format_finding_item(uc)}")
        feedback_lines.append("")

    ia = dims.get("intent_alignment", {})
    if isinstance(ia, dict) and ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in _extract_finding_items(ia, "unaddressed_requirements"):
            feedback_lines.append(f"- Unaddressed requirement: {_format_finding_item(req)}")
        for creep in _extract_finding_items(ia, "scope_creep"):
            feedback_lines.append(f"- Scope creep: {_format_finding_item(creep)}")
        feedback_lines.append("")

    gd = dims.get("gap_detection", {})
    if isinstance(gd, dict) and gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in _extract_finding_items(gd, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    vs = dims.get("validation_sufficiency", {})
    if isinstance(vs, dict) and vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in _extract_finding_items(vs, "weak_checks"):
            feedback_lines.append(f"- {_format_finding_item(wc)}")
        feedback_lines.append("")

    gs = dims.get("gap_sufficiency", {})
    if isinstance(gs, dict) and gs.get("status") == "fail":
        feedback_lines.append("### Missed Gaps")
        for mg in _extract_finding_items(gs, "missed_gaps"):
            feedback_lines.append(f"- {_format_finding_item(mg)}")
        feedback_lines.append("")

    findings_text = "\n".join(feedback_lines) if feedback_lines else "(no specific findings)"

    return f"""\
# Task: Address Verifier Feedback (Targeted Revision)

The current plan.json passed structural validation but failed Phase B
cross-model verification. Treat the current plan as suspect wherever it
conflicts with the epic contract or verifier findings.

## Original Epic Contract

<epic>
{epic_md}
</epic>

## Rules

1. The epic contract wins over the current plan.
2. You MAY rewrite any affected story, journey, checkpoint, or validation path.
3. Preserve untouched sections only if they still fit the epic and findings.
4. Keep `scope.modify` paths pointing to files that exist on disk RIGHT NOW.
   Use the Glob and Read tools to verify file paths if unsure.
5. If verifier feedback shows the current framing is wrong, fix the framing
   instead of patching around it.
6. Output only the complete JSON object matching the provided schema.
7. Use the StructuredOutput tool for the final answer.

---

## Current Plan

<current_plan>
{plan_json_str}
</current_plan>

---

## Must-Fix Findings

{findings_text}

---

Address the findings above and emit the complete JSON object.
Do NOT omit any existing fields unless you are replacing them with corrected
content in the revised plan."""


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------


def _parse_structured_plan(result) -> Plan:
    """Parse a dispatch result into a validated Plan model."""
    text = result.output.strip()

    fence_match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    json_text = fence_match.group(1).strip() if fence_match else text

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        pos = exc.pos or 0
        context_start = max(0, pos - 200)
        context_end = min(len(json_text), pos + 200)
        error_context = json_text[context_start:context_end]
        marker_pos = pos - context_start
        marker_line = " " * marker_pos + "^ ERROR HERE"
        raise PlanGenerationError(
            f"Planner output is not valid JSON: {exc}\n"
            f"Context around error (char {pos}):\n"
            f"{error_context}\n{marker_line}"
        ) from exc
    try:
        return Plan.model_validate(data)
    except Exception as exc:
        raise PlanGenerationError(f"Plan JSON failed Pydantic validation: {exc}") from exc


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def generate_plan(
    epic_dir: Path,
    config: EpicConfig | None = None,
) -> tuple[Path, Path]:
    """Generate PLAN.md and plan.json from the epic body.

    The planner is dispatched as a tool-equipped agent that explores the
    codebase itself. It receives only the epic body and JSON schema.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain EPIC.md from ingestion.
        config: Optional epic config for model/budget overrides.

    Returns:
        Tuple of (plan_md_path, plan_json_path).

    Raises:
        PlanGenerationError: If EPIC.md is missing, dispatch fails, or
            output cannot be parsed.
    """
    epic_md = _read_epic_md(epic_dir)
    epic_number = _read_epic_number(epic_dir)

    prompt = _build_planner_prompt(
        epic_md=epic_md,
        epic_number=epic_number,
    )

    prompt_tokens = len(prompt) // 4
    planner_model = config.models.planner if config else "sonnet"

    logger.info(
        "Dispatching %s planner for epic #%d (%d chars, ~%d tokens)",
        planner_model,
        epic_number,
        len(prompt),
        prompt_tokens,
    )

    mcp_servers, timeout = get_dispatch_params("planning", config)
    result = dispatch_agent(
        prompt=prompt,
        model=planner_model,
        json_schema=Plan.model_json_schema(),
        cwd=PROJECT_ROOT,
        mcp_servers=mcp_servers,
        timeout=timeout,
        role="planner",
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    logger.info(
        "Planner output length: %d chars, turns: %s",
        len(result.output),
        result.turns or "unknown",
    )

    plan = _parse_structured_plan(result)

    plan_json_path = epic_dir / "plan.json"
    plan_json_path.write_text(
        json.dumps(plan.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote plan.json to %s", plan_json_path)

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
            f"Run ingestion first.",
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
