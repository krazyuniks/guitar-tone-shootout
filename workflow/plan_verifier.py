"""Phase B: AI plan verification (~$1-2 per invocation).

Dispatches a Sonnet agent to holistically verify the plan against the
original epic intent. Checks 5 dimensions: journey completeness,
transition coverage, intent alignment, gap detection, and validation
sufficiency.

This runs AFTER Phase A deterministic validation passes. Phase B catches
what deterministic checks cannot: narrative completeness, intent alignment,
and logical gaps between stories.

Reference: Research doc Section 8.4 Decision 8.

One revision cycle is budgeted: planner -> verifier -> planner -> verifier.
If the second attempt also fails Phase B, exit to human.

Usage:
    python scripts/plan_verifier.py <epic_number>
"""

import json
import logging
import sys
from pathlib import Path

from workflow.dispatch import (
    BUDGET_DEFAULTS,
    FALLBACK_MODELS,
    dispatch_with_fallback,
)
from workflow.models import Plan, render_plan_md
from workflow.plan_generator import (
    PlanGenerationError,
    _parse_structured_plan,
    build_verifier_revision_prompt,
)
from workflow.plan_validator import validate_plan

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
SCHEMAS_DIR = PROJECT_ROOT / "workflow" / "schemas"

logger = logging.getLogger(__name__)


class PlanVerificationError(Exception):
    """Raised when plan verification fails unrecoverably."""


# ---------------------------------------------------------------------------
# Schema loader
# ---------------------------------------------------------------------------


def _load_verifier_schema() -> dict:
    """Load the verifier-result.schema.json for --json-schema."""
    schema_path = SCHEMAS_DIR / "verifier-result.schema.json"
    if not schema_path.is_file():
        raise PlanVerificationError(
            f"Verifier result schema not found at {schema_path}. "
            "Ensure Step 1 schemas are in place."
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Verifier prompt construction
# ---------------------------------------------------------------------------


def _build_verifier_prompt(
    plan_json: dict,
    epic_md: str,
    context_md: str,
) -> str:
    """Construct the Sonnet verifier prompt."""
    plan_json_str = json.dumps(plan_json, indent=2)

    prompt = f"""\
# Task: Verify Epic Plan

You are a plan verifier for the GTS (Guitar Tone Shootout) project. Your job
is to check whether a generated plan fully and correctly addresses the epic's
requirements. You do NOT fix anything. You only report findings.

You must check 5 dimensions and return structured JSON output.

---

## Input 1: Original Epic (from GitHub)

<epic>
{epic_md}
</epic>

## Input 2: Assembled Context

<context>
{context_md}
</context>

## Input 3: Generated Plan (plan.json)

<plan>
{plan_json_str}
</plan>

---

## Verification Dimensions

Check each dimension independently. For each, set status to "pass" or "fail".

### 1. Journey Completeness

Do the user journeys cover the full scope of the epic? Walk through each
journey narrative and verify:
- Every step in the narrative has a corresponding story that builds it
- Every step has a validation checkpoint that verifies it (either directly
  or as part of a broader checkpoint)
- Flag any step in a journey that no story addresses

Set `gaps` to an empty array if all journeys are complete.

### 2. Transition Coverage

Are all `critical_transitions` in the journeys covered by validation
checkpoints? For each transition:
- There must be a checkpoint verifying the source page renders correctly
- There must be a checkpoint verifying the transition mechanism works
  (link exists, form submits, etc.)
- There must be a checkpoint verifying the target page renders correctly

Flag transitions that fall between checkpoints (i.e., no checkpoint
verifies them). Set `uncovered` to an empty array if all transitions
are covered.

### 3. Intent Alignment

Does the plan deliver what the epic asks for? Compare the epic's
requirements against the plan's stories:
- Flag epic requirements that have no corresponding story
  (unaddressed_requirements)
- Flag stories that address requirements not in the epic
  (scope_creep)

Set both arrays to empty if alignment is perfect.

### 4. Gap Detection

Are there logical gaps between stories? Walk the dependency chain for
each feature:
- entity -> ORM model -> repository -> service -> API endpoint ->
  page template -> navigation link
- Every link in the chain must exist in some story's scope
- If Story 1 creates an entity and Story 3 builds UI for it, but no
  story creates the API endpoint connecting them, flag the gap

Set `gaps` to an empty array if no logical gaps exist.

### 5. Validation Sufficiency

Are the validation checkpoints strong enough to catch real failures?
For each checkpoint, ask: "If this check passes, does it prove the
feature works, or could it false-green?"

Flag checks that:
- Verify existence but not function (e.g., "page returns 200" without
  checking content)
- Miss critical user-facing behaviour
- Could pass even if the feature is broken

Set `weak_checks` to an empty array if all checkpoints are sufficient.

---

## What You Do NOT Check

- Whether implementation notes are correct (runtime discovery)
- Whether file paths in scope are the best choice (planner's domain)
- Whether story sizing is optimal (learned from experience)
- Subjective plan quality (human's job at Decision Gate)

---

## Output

Your ENTIRE response must be a single JSON object — no markdown, no analysis text,
no explanation before or after. Output ONLY the JSON object.

The JSON must have this structure:
- "status": "pass" or "fail" (pass only if ALL 5 dimensions pass)
- "dimensions": object with keys for each dimension, each containing "status" and "findings"
- "summary": brief overall summary string

Be rigorous but fair. Flag real issues, not stylistic preferences.
"""

    return prompt


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _parse_verifier_result(result_output: str) -> dict:
    """Parse the verifier agent's output as JSON.

    The prompt instructs the agent to return ONLY a JSON object.
    Agents commonly wrap JSON in markdown code fences, so we strip those.
    """
    text = (result_output or "").strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanVerificationError(
            f"Verifier did not return valid JSON: {exc}\nOutput (first 500 chars): {text[:500]}"
        ) from exc
    if not isinstance(data, dict) or "status" not in data:
        raise PlanVerificationError(
            f"Verifier JSON missing 'status' field. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        )
    return data


def _is_verifier_pass(result: dict) -> bool:
    """Check if the verifier result indicates an overall pass."""
    return result.get("status") == "pass"


def _extract_dimension_failures(result: dict) -> list[str]:
    """Extract a summary of failed dimensions for logging."""
    failures = []
    for dimension in [
        "journey_completeness",
        "transition_coverage",
        "intent_alignment",
        "gap_detection",
        "validation_sufficiency",
    ]:
        dim = result.get(dimension, {})
        if isinstance(dim, dict) and dim.get("status") == "fail":
            failures.append(dimension)
    return failures


# ---------------------------------------------------------------------------
# Decision Gate
# ---------------------------------------------------------------------------


class DecisionGateResult:
    """Result from the human Decision Gate."""

    def __init__(self, decision: str, reason: str = "") -> None:
        if decision not in ("approve", "revise", "reject"):
            raise ValueError(f"Invalid decision: {decision}. Must be approve/revise/reject.")
        self.decision = decision
        self.reason = reason

    @property
    def approved(self) -> bool:
        return self.decision == "approve"

    @property
    def needs_revision(self) -> bool:
        return self.decision == "revise"

    @property
    def rejected(self) -> bool:
        return self.decision == "reject"

    def __repr__(self) -> str:
        return f"DecisionGateResult(decision={self.decision!r}, reason={self.reason!r})"


def present_decision_gate(
    plan_md_path: Path,
    verifier_result: dict,
) -> DecisionGateResult:
    """Present the human with PLAN.md + verifier report and get a decision."""
    # Display plan location
    print("\n" + "=" * 70)
    print("DECISION GATE")
    print("=" * 70)
    print(f"\nPlan ready for review: {plan_md_path}")
    print(f"Verifier status: {verifier_result.get('status', 'unknown')}")

    # Show dimension statuses
    print("\nVerifier dimensions:")
    for dimension in [
        "journey_completeness",
        "transition_coverage",
        "intent_alignment",
        "gap_detection",
        "validation_sufficiency",
    ]:
        dim = verifier_result.get(dimension, {})
        status = dim.get("status", "unknown") if isinstance(dim, dict) else "unknown"
        icon = "PASS" if status == "pass" else "FAIL"
        print(f"  [{icon}] {dimension}")

    # Show failures if any
    failed_dims = _extract_dimension_failures(verifier_result)
    if failed_dims:
        print(f"\nFailed dimensions: {', '.join(failed_dims)}")
        for dim_name in failed_dims:
            dim = verifier_result.get(dim_name, {})
            if not isinstance(dim, dict):
                continue
            for key in [
                "gaps",
                "uncovered",
                "unaddressed_requirements",
                "scope_creep",
                "weak_checks",
            ]:
                items = dim.get(key, [])
                if items:
                    print(f"\n  {dim_name}.{key}:")
                    for item in items[:3]:
                        if isinstance(item, dict):
                            print(f"    - {json.dumps(item)}")
                        else:
                            print(f"    - {item}")
                    if len(items) > 3:
                        print(f"    ... and {len(items) - 3} more")

    print("\nOptions:")
    print("  [a] Approve — proceed to execution")
    print("  [r] Revise  — edit plan.json and PLAN.md, then re-validate")
    print("  [x] Reject  — exit, planning artefacts not committed")
    print()

    while True:
        try:
            choice = input("Decision [a/r/x]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nRejected (interrupted)")
            return DecisionGateResult("reject", reason="User interrupted")

        if choice == "a":
            return DecisionGateResult("approve")
        elif choice == "r":
            reason = input("Revision notes (optional): ").strip()
            return DecisionGateResult("revise", reason=reason)
        elif choice == "x":
            reason = input("Rejection reason (optional): ").strip()
            return DecisionGateResult("reject", reason=reason)
        else:
            print("Invalid choice. Enter 'a', 'r', or 'x'.")


# ---------------------------------------------------------------------------
# Core verification function
# ---------------------------------------------------------------------------


def verify_plan(
    epic_dir: Path,
) -> dict:
    """Run Phase B AI verification on the plan."""
    # Read inputs
    plan_json_path = epic_dir / "plan.json"
    epic_md_path = epic_dir / "EPIC.md"
    context_md_path = epic_dir / "CONTEXT.md"

    if not plan_json_path.is_file():
        raise PlanVerificationError(f"plan.json not found at {plan_json_path}")
    if not epic_md_path.is_file():
        raise PlanVerificationError(f"EPIC.md not found at {epic_md_path}")
    if not context_md_path.is_file():
        raise PlanVerificationError(f"CONTEXT.md not found at {context_md_path}")

    plan_json = json.loads(plan_json_path.read_text(encoding="utf-8"))
    epic_md = epic_md_path.read_text(encoding="utf-8")
    context_md = context_md_path.read_text(encoding="utf-8")

    # Build the verifier prompt
    prompt = _build_verifier_prompt(
        plan_json=plan_json,
        epic_md=epic_md,
        context_md=context_md,
    )

    logger.info(
        "Dispatching Sonnet verifier (%d chars, ~%d tokens)",
        len(prompt),
        len(prompt) // 4,
    )

    # Dispatch via Sonnet with Haiku fallback
    validation_budget = BUDGET_DEFAULTS["validation"]
    verifier_budget_usd = max(float(validation_budget["max_budget_usd"]), 2.0)
    verifier_max_turns = max(int(validation_budget["max_turns"]), 20)

    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model="sonnet",
        fallback_model=FALLBACK_MODELS["sonnet"],
        tools=[],
        max_turns=verifier_max_turns,
        max_budget_usd=verifier_budget_usd,
        json_schema=None,
        cwd=PROJECT_ROOT,
        no_mcp=True,
    )

    if not result.success:
        raise PlanVerificationError(
            f"Verifier dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    # Parse structured output
    verifier_result = _parse_verifier_result(result.output)

    logger.info(
        "Verifier result: status=%s, cost=$%s",
        verifier_result.get("status", "unknown"),
        result.cost_usd or "unknown",
    )

    return verifier_result


# ---------------------------------------------------------------------------
# Full verification with revision cycle
# ---------------------------------------------------------------------------


def verify_with_revision_cycle(
    epic_dir: Path,
) -> tuple[dict, bool]:
    """Run the full two-phase verification with one revision cycle."""

    # Phase A: Deterministic validation (attempt 1)
    logger.info("Running Phase A validation (attempt 1)...")
    phase_a_result = validate_plan(epic_dir)

    if not phase_a_result.valid:
        logger.warning(
            "Phase A failed with %d errors. Re-invoking planner...",
            len(phase_a_result.errors),
        )

        # Re-invoke planner with validation errors
        try:
            _regenerate_plan_with_errors(epic_dir, phase_a_result.error_messages())
        except PlanGenerationError as exc:
            logger.error("Plan regeneration failed: %s", exc)
            return (
                {"status": "fail", "phase_a_errors": phase_a_result.error_messages()},
                False,
            )

        # Re-run Phase A on revised plan
        logger.info("Running Phase A validation (attempt 2, after planner revision)...")
        phase_a_result = validate_plan(epic_dir)
        if not phase_a_result.valid:
            logger.error(
                "Phase A still fails after planner revision (%d errors). Exiting to human.",
                len(phase_a_result.errors),
            )
            return (
                {"status": "fail", "phase_a_errors": phase_a_result.error_messages()},
                False,
            )

    logger.info("Phase A passed. Running Phase B verification...")

    # Phase B: AI verification (attempt 1)
    try:
        verifier_result = verify_plan(epic_dir)
    except PlanVerificationError as exc:
        logger.error("Phase B dispatch failed: %s", exc)
        return ({"status": "fail", "error": str(exc)}, False)

    if _is_verifier_pass(verifier_result):
        logger.info("Phase B passed. Plan verified.")
        return (verifier_result, True)

    # Phase B failed — feed verifier output back to planner for revision
    failed_dims = _extract_dimension_failures(verifier_result)
    logger.warning(
        "Phase B failed (dimensions: %s). Re-invoking planner with verifier feedback...",
        ", ".join(failed_dims),
    )

    try:
        _regenerate_plan_with_verifier_feedback(epic_dir, verifier_result)
    except PlanGenerationError as exc:
        logger.error("Plan regeneration (verifier feedback) failed: %s", exc)
        return (verifier_result, False)

    # Re-run Phase A on revised plan (must still pass after revision)
    logger.info("Running Phase A validation (after verifier revision)...")
    phase_a_result = validate_plan(epic_dir)
    if not phase_a_result.valid:
        logger.error(
            "Phase A fails after verifier revision (%d errors). Exiting to human.",
            len(phase_a_result.errors),
        )
        return (
            {"status": "fail", "phase_a_errors": phase_a_result.error_messages()},
            False,
        )

    # Phase B: AI verification (attempt 2 — final)
    logger.info("Running Phase B verification (attempt 2, final)...")
    try:
        verifier_result = verify_plan(epic_dir)
    except PlanVerificationError as exc:
        logger.error("Phase B dispatch failed on second attempt: %s", exc)
        return ({"status": "fail", "error": str(exc)}, False)

    if _is_verifier_pass(verifier_result):
        logger.info("Phase B passed on second attempt. Plan verified.")
        return (verifier_result, True)

    # Second attempt also failed — exit to human
    failed_dims = _extract_dimension_failures(verifier_result)
    logger.error(
        "Phase B still fails after revision (dimensions: %s). Exiting to human.",
        ", ".join(failed_dims),
    )
    return (verifier_result, False)


# ---------------------------------------------------------------------------
# Plan regeneration helpers
# ---------------------------------------------------------------------------


def _read_original_prompt_context(epic_dir: Path) -> tuple[str, int]:
    """Read CONTEXT.md and extract epic number for prompt reconstruction."""
    import re as _re

    context_path = epic_dir / "CONTEXT.md"
    context = context_path.read_text(encoding="utf-8") if context_path.is_file() else ""

    match = _re.match(r"^E(\d+)$", epic_dir.name)
    epic_number = int(match.group(1)) if match else 0

    return context, epic_number


def _write_plan_from_model(plan: Plan, epic_dir: Path) -> None:
    """Write plan.json and PLAN.md from a validated Plan model."""
    (epic_dir / "plan.json").write_text(
        json.dumps(plan.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (epic_dir / "PLAN.md").write_text(render_plan_md(plan), encoding="utf-8")
    logger.info("Wrote revised plan.json and PLAN.md")


def _regenerate_plan_with_errors(
    epic_dir: Path,
    validation_errors: list[str],
) -> None:
    """Re-invoke the planner with Phase A validation errors.

    Uses structured output (--json-schema, tools=[]) and parses the
    result with Pydantic.
    """
    from workflow.plan_generator import (
        _build_planner_prompt,
        build_revision_prompt,
    )

    context, epic_number = _read_original_prompt_context(epic_dir)

    # Rebuild the original prompt
    original_prompt = _build_planner_prompt(
        context=context,
        epic_number=epic_number,
    )

    # Build revision prompt with errors
    revision_prompt = build_revision_prompt(original_prompt, validation_errors)

    logger.info("Dispatching planner revision (Phase A errors, %d chars)", len(revision_prompt))

    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=revision_prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=[],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        json_schema=None,
        cwd=PROJECT_ROOT,
        no_mcp=True,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner revision dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    plan = _parse_structured_plan(result)
    _write_plan_from_model(plan, epic_dir)


def _regenerate_plan_with_verifier_feedback(
    epic_dir: Path,
    verifier_result: dict,
) -> None:
    """Re-invoke the planner with Phase B verifier feedback.

    Uses structured output (--json-schema, tools=[]) and parses the
    result with Pydantic.
    """
    from workflow.plan_generator import _build_planner_prompt

    context, epic_number = _read_original_prompt_context(epic_dir)

    # Rebuild the original prompt
    original_prompt = _build_planner_prompt(
        context=context,
        epic_number=epic_number,
    )

    # Build revision prompt with verifier feedback
    revision_prompt = build_verifier_revision_prompt(original_prompt, verifier_result)

    logger.info("Dispatching planner revision (verifier feedback, %d chars)", len(revision_prompt))

    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=revision_prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=[],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        json_schema=None,
        cwd=PROJECT_ROOT,
        no_mcp=True,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner revision (verifier feedback) dispatch failed "
            f"(exit_code={result.exit_code}). Output: {result.output[:500]}"
        )

    plan = _parse_structured_plan(result)
    _write_plan_from_model(plan, epic_dir)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python scripts/plan_verifier.py <epic_number> [--full-cycle]."""
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <epic_number> [--full-cycle]",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(f"Error: epic_number must be an integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    full_cycle = "--full-cycle" in sys.argv

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(f"Error: Epic directory not found: {epic_dir}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if full_cycle:
        verifier_result, success = verify_with_revision_cycle(epic_dir)

        if success:
            print(f"\nPlan verification PASSED for epic #{epic_number}")
            print("All 5 dimensions verified successfully.")
        else:
            print(f"\nPlan verification FAILED for epic #{epic_number}")
            failed = _extract_dimension_failures(verifier_result)
            if failed:
                print(f"Failed dimensions: {', '.join(failed)}")
            if "phase_a_errors" in verifier_result:
                print("Phase A errors:")
                for err in verifier_result["phase_a_errors"]:
                    print(f"  - {err}")

        sys.exit(0 if success else 1)

    else:
        try:
            verifier_result = verify_plan(epic_dir)
        except PlanVerificationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        status = verifier_result.get("status", "unknown")
        print(f"\nPhase B verification result: {status}")

        for dimension in [
            "journey_completeness",
            "transition_coverage",
            "intent_alignment",
            "gap_detection",
            "validation_sufficiency",
        ]:
            dim = verifier_result.get(dimension, {})
            dim_status = dim.get("status", "unknown") if isinstance(dim, dict) else "unknown"
            print(f"  [{dim_status.upper()}] {dimension}")

        print(f"\nFull result:\n{json.dumps(verifier_result, indent=2)}")

        sys.exit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
