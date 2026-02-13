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

from scripts.dispatch import (
    BUDGET_DEFAULTS,
    FALLBACK_MODELS,
    dispatch_with_fallback,
    get_tools_for_role,
)
from scripts.plan_generator import (
    PlanGenerationError,
    build_planner_output_schema,
    build_verifier_revision_prompt,
)
from scripts.plan_validator import validate_plan

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
SCHEMAS_DIR = PROJECT_ROOT / "scripts" / "schemas"

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
    decisions: dict | None = None,
) -> str:
    """Construct the Sonnet verifier prompt.

    The verifier receives the full plan, original epic intent, assembled
    context, and locked scope decisions. It checks 5 dimensions and
    returns structured output.
    """
    plan_json_str = json.dumps(plan_json, indent=2)

    decisions_text = ""
    if decisions:
        lines = ["## Locked Scope Decisions", ""]
        for question, answer in decisions.items():
            lines.append(f"**Q:** {question}")
            lines.append(f"**A:** {answer}")
            lines.append("")
        decisions_text = "\n".join(lines)

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

{decisions_text}

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

Return a JSON object with the structure defined by the --json-schema.
The overall status is "pass" only if ALL 5 dimensions pass.

Be rigorous but fair. Flag real issues, not stylistic preferences.
"""

    return prompt


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _parse_verifier_result(result_output: str, structured_output: dict | None) -> dict:
    """Parse the verifier agent's output into a structured result dict.

    Tries structured_output first (from --json-schema), then falls back
    to extracting JSON from the raw output text.

    Returns:
        Dict conforming to verifier-result.schema.json.

    Raises:
        PlanVerificationError: If output cannot be parsed.
    """
    # Try structured output first
    if structured_output and isinstance(structured_output, dict) and "status" in structured_output:
        return structured_output

    # Try to extract JSON from raw output
    if result_output.strip():
        # The output may be wrapped in Claude's JSON output format
        try:
            parsed = json.loads(result_output)
            if isinstance(parsed, dict):
                # Check if the result is nested
                if "result" in parsed and isinstance(parsed["result"], dict):
                    candidate = parsed["result"]
                    if "status" in candidate:
                        return candidate
                if "status" in parsed:
                    return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON in the output text
        import re

        for match in re.finditer(r"\{", result_output):
            start = match.start()
            depth = 0
            for i in range(start, len(result_output)):
                if result_output[i] == "{":
                    depth += 1
                elif result_output[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate_str = result_output[start : i + 1]
                        try:
                            candidate = json.loads(candidate_str)
                            if isinstance(candidate, dict) and "status" in candidate:
                                return candidate
                        except json.JSONDecodeError:
                            pass
                        break

    raise PlanVerificationError(
        "Could not parse verifier output into structured result. "
        f"Raw output (first 500 chars): {result_output[:500]}"
    )


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
    """Result from the human Decision Gate.

    Three outcomes:
    - approve: Proceed to execution
    - revise: Human edited plan, re-run Phase A + B (no planner re-invocation)
    - reject: Exit to human, planning artefacts NOT committed
    """

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
    """Present the human with PLAN.md + verifier report and get a decision.

    Three outcomes:
    - approve: Proceed to commit + push, then start execution
    - revise: Human edits plan.json + PLAN.md directly, re-run Phase A + B.
              No planner re-invocation — the human IS the planner for revisions.
    - reject: Log exit_to_human event, exit. Planning artefacts NOT committed.
              Human restarts from step 1 (re-ingest), step 3 (re-scope), or
              step 4 (re-plan).

    Args:
        plan_md_path: Path to PLAN.md for the human to review.
        verifier_result: Structured verifier output to display alongside the plan.

    Returns:
        DecisionGateResult with the human's decision.
    """
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
            # Show first few items from the failure details
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
    decisions: dict | None = None,
) -> dict:
    """Run Phase B AI verification on the plan.

    Dispatches a Sonnet agent to check the plan against the epic intent
    across 5 dimensions. Returns structured output conforming to
    verifier-result.schema.json.

    Args:
        epic_dir: Path to the epic directory containing plan.json,
            EPIC.md, and CONTEXT.md.
        decisions: Locked scope decisions from interactive Phase 2.

    Returns:
        Dict conforming to verifier-result.schema.json.

    Raises:
        PlanVerificationError: If verification fails unrecoverably.
    """
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

    # Load the verifier result schema for --json-schema
    verifier_schema = _load_verifier_schema()

    # Build the verifier prompt
    prompt = _build_verifier_prompt(
        plan_json=plan_json,
        epic_md=epic_md,
        context_md=context_md,
        decisions=decisions,
    )

    logger.info(
        "Dispatching Sonnet verifier (%d chars, ~%d tokens)",
        len(prompt),
        len(prompt) // 4,
    )

    # Dispatch via Sonnet with Haiku fallback
    validation_budget = BUDGET_DEFAULTS["validation"]
    # Verifier needs more budget than a standard validation check
    verifier_budget_usd = max(float(validation_budget["max_budget_usd"]), 2.0)
    verifier_max_turns = max(int(validation_budget["max_turns"]), 20)

    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model="sonnet",
        fallback_model=FALLBACK_MODELS["sonnet"],
        tools=get_tools_for_role("validation_api"),
        max_turns=verifier_max_turns,
        max_budget_usd=verifier_budget_usd,
        json_schema=verifier_schema,
        cwd=PROJECT_ROOT,
    )

    if not result.success:
        raise PlanVerificationError(
            f"Verifier dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    # Parse structured output
    verifier_result = _parse_verifier_result(result.output, result.structured_output)

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
    decisions: dict | None = None,
) -> tuple[dict, bool]:
    """Run the full two-phase verification with one revision cycle.

    Flow:
    1. Run Phase A (deterministic validation)
    2. If Phase A fails, re-invoke planner with validation errors
    3. Run Phase A again on revised plan
    4. If Phase A passes, run Phase B (AI verification)
    5. If Phase B fails, feed verifier output back to planner for revision
    6. Run Phase A + B on revised plan
    7. If second attempt also fails, exit to human

    Args:
        epic_dir: Path to the epic directory.
        decisions: Locked scope decisions.

    Returns:
        Tuple of (verifier_result_dict, success_bool).
        On success, verifier_result contains the passing verification.
        On failure, verifier_result contains the last failing verification.
    """
    if decisions is None:
        decisions = {}

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
            _regenerate_plan_with_errors(epic_dir, phase_a_result.error_messages(), decisions)
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
        verifier_result = verify_plan(epic_dir, decisions)
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
        _regenerate_plan_with_verifier_feedback(epic_dir, verifier_result, decisions)
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
        verifier_result = verify_plan(epic_dir, decisions)
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
# Structured plan extraction
# ---------------------------------------------------------------------------


def _extract_structured_plan(result) -> tuple[str, dict]:
    """Extract plan_md and plan_json from a dispatch result.

    Tries structured_output first (from --json-schema), then falls back
    to _parse_plan_output() for text delimiter extraction.

    Args:
        result: AgentResult from dispatch_with_fallback.

    Returns:
        Tuple of (plan_md_content, plan_json_dict).

    Raises:
        PlanGenerationError: If neither structured nor text output can be parsed.
    """
    from scripts.plan_generator import _parse_plan_output

    # Try structured output first (from --json-schema)
    so = result.structured_output
    if so and isinstance(so, dict):
        # Claude Code wraps the JSON schema result inside the envelope.
        # The envelope has {"result": <json-schema output>} when using
        # --output-format json + --json-schema together. dispatch.py
        # already extracts result.output as the text, but
        # structured_output holds the full envelope.
        candidate = so

        # If the envelope wraps a "result" field that is itself a dict
        # with plan_md/plan_json, use that.
        if "result" in candidate and isinstance(candidate["result"], dict):
            candidate = candidate["result"]

        if "plan_md" in candidate and "plan_json" in candidate:
            plan_md = candidate["plan_md"]
            plan_json = candidate["plan_json"]
            if isinstance(plan_md, str) and isinstance(plan_json, dict):
                return plan_md, plan_json

    # Try parsing the text output from result.output as JSON
    # (--json-schema output may arrive as the text result field)
    if result.output and result.output.strip():
        try:
            parsed = json.loads(result.output)
            if isinstance(parsed, dict) and "plan_md" in parsed and "plan_json" in parsed:
                return parsed["plan_md"], parsed["plan_json"]
        except (json.JSONDecodeError, ValueError):
            pass

    # Fall back to text delimiter parsing
    return _parse_plan_output(result.output)


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


def _regenerate_plan_with_errors(
    epic_dir: Path,
    validation_errors: list[str],
    decisions: dict,
) -> None:
    """Re-invoke the planner with Phase A validation errors.

    Builds a revision prompt containing the original planning prompt plus
    the specific validation errors, then dispatches the planner again.
    Uses --json-schema to force structured output with plan_md and plan_json
    fields, avoiding fragile text delimiter parsing.
    """
    from scripts.plan_generator import (
        _build_planner_prompt,
        _format_decisions,
        _load_plan_schema,
        build_revision_prompt,
    )

    context, epic_number = _read_original_prompt_context(epic_dir)
    plan_schema = _load_plan_schema()
    decisions_text = _format_decisions(decisions)

    # Rebuild the original prompt
    original_prompt = _build_planner_prompt(
        context=context,
        decisions_text=decisions_text,
        plan_schema=plan_schema,
        epic_number=epic_number,
    )

    # Build revision prompt with errors
    revision_prompt = build_revision_prompt(original_prompt, validation_errors)

    # Build wrapper schema for structured output
    output_schema = build_planner_output_schema(plan_schema)

    logger.info("Dispatching planner revision (Phase A errors, %d chars)", len(revision_prompt))

    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=revision_prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=get_tools_for_role("planning"),
        skills=["gts-architecture", "gts-backend-dev", "gts-frontend-dev"],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        json_schema=output_schema,
        cwd=PROJECT_ROOT,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner revision dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    # Extract plan_md and plan_json from structured output
    plan_md_content, plan_json_dict = _extract_structured_plan(result)

    (epic_dir / "PLAN.md").write_text(plan_md_content, encoding="utf-8")
    (epic_dir / "plan.json").write_text(
        json.dumps(plan_json_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Wrote revised PLAN.md and plan.json")


def _regenerate_plan_with_verifier_feedback(
    epic_dir: Path,
    verifier_result: dict,
    decisions: dict,
) -> None:
    """Re-invoke the planner with Phase B verifier feedback.

    Builds a revision prompt containing the original planning prompt plus
    the structured verifier output, then dispatches the planner again.
    Uses --json-schema to force structured output with plan_md and plan_json
    fields, avoiding fragile text delimiter parsing.
    """
    from scripts.plan_generator import (
        _build_planner_prompt,
        _format_decisions,
        _load_plan_schema,
    )

    context, epic_number = _read_original_prompt_context(epic_dir)
    plan_schema = _load_plan_schema()
    decisions_text = _format_decisions(decisions)

    # Rebuild the original prompt
    original_prompt = _build_planner_prompt(
        context=context,
        decisions_text=decisions_text,
        plan_schema=plan_schema,
        epic_number=epic_number,
    )

    # Build revision prompt with verifier feedback
    revision_prompt = build_verifier_revision_prompt(original_prompt, verifier_result)

    # Build wrapper schema for structured output
    output_schema = build_planner_output_schema(plan_schema)

    logger.info("Dispatching planner revision (verifier feedback, %d chars)", len(revision_prompt))

    planning_budget = BUDGET_DEFAULTS["planning"]
    result = dispatch_with_fallback(
        prompt=revision_prompt,
        primary_model="opus",
        fallback_model=FALLBACK_MODELS["opus"],
        tools=get_tools_for_role("planning"),
        skills=["gts-architecture", "gts-backend-dev", "gts-frontend-dev"],
        max_turns=int(planning_budget["max_turns"]),
        max_budget_usd=float(planning_budget["max_budget_usd"]),
        json_schema=output_schema,
        cwd=PROJECT_ROOT,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner revision (verifier feedback) dispatch failed "
            f"(exit_code={result.exit_code}). Output: {result.output[:500]}"
        )

    # Extract plan_md and plan_json from structured output
    plan_md_content, plan_json_dict = _extract_structured_plan(result)

    (epic_dir / "PLAN.md").write_text(plan_md_content, encoding="utf-8")
    (epic_dir / "plan.json").write_text(
        json.dumps(plan_json_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Wrote revised PLAN.md and plan.json (verifier feedback)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python scripts/plan_verifier.py <epic_number> [--full-cycle] [--decisions file.json]."""
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <epic_number> [--full-cycle] [--decisions file.json]",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(f"Error: epic_number must be an integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    full_cycle = "--full-cycle" in sys.argv

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
        print(f"Error: Epic directory not found: {epic_dir}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if full_cycle:
        # Run the full verification with revision cycle
        verifier_result, success = verify_with_revision_cycle(epic_dir, decisions)

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
        # Run Phase B verification only (Phase A should have passed already)
        try:
            verifier_result = verify_plan(epic_dir, decisions)
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
