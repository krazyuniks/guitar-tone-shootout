"""Phase A: Deterministic plan validation ($0 AI cost).

Validates plan.json against the Pydantic Plan model and checks 7
structural properties that are mechanical and instant to verify. This
runs before Phase B (AI verification) to catch structural errors without
spending any AI tokens.

Check 1 (schema conformance) is eliminated — Pydantic validation in
the plan generator already enforces it. Check 8 (command coverage)
runs but only produces warnings, not errors.

Reference: Research doc Section 8.4 Decision 8.

Usage:
    python -m workflow.plan_validator <epic_number>
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from workflow.models import Plan
from workflow.validation import _match_command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)

# Maximum total budget across all stories (sanity check)
MAX_TOTAL_BUDGET_USD = 50.0


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationError:
    """A single validation error with category and detail."""

    check: str
    message: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.message}"


@dataclass
class ValidationResult:
    """Structured result from Phase A deterministic validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def error_messages(self) -> list[str]:
        """Return error messages formatted for injection into planner retry prompt."""
        return [str(e) for e in self.errors]


# ---------------------------------------------------------------------------
# Check 2: Referential integrity
# ---------------------------------------------------------------------------


def _check_referential_integrity(plan: Plan) -> list[ValidationError]:
    """Check 2: All cross-references are valid.

    - Every truths_addressed ID exists in observable_truths
    - Every checkpoint after_story references a valid story_id
    - Every journey truths_covered ID exists in observable_truths
    """
    errors: list[ValidationError] = []

    truth_ids = {t.id for t in plan.observable_truths}
    story_ids = {s.story_id for s in plan.stories}

    # truths_addressed in stories
    for story in plan.stories:
        for tid in story.truths_addressed:
            if tid not in truth_ids:
                errors.append(
                    ValidationError(
                        check="referential_integrity",
                        message=f"Story '{story.story_id}' references truth ID {tid} in "
                        f"truths_addressed, but no observable_truth with that ID exists. "
                        f"Valid IDs: {sorted(truth_ids)}",
                    )
                )

    # after_story in validation_checkpoints
    for cp in plan.validation_checkpoints:
        if cp.after_story not in story_ids:
            errors.append(
                ValidationError(
                    check="referential_integrity",
                    message=f"Checkpoint after_story '{cp.after_story}' does not match "
                    f"any story_id. Valid story_ids: {sorted(story_ids)}",
                )
            )

    # truths_covered in user_journeys
    for journey in plan.user_journeys:
        for tid in journey.truths_covered:
            if tid not in truth_ids:
                errors.append(
                    ValidationError(
                        check="referential_integrity",
                        message=f"Journey '{journey.journey_id}' references truth ID {tid} "
                        f"in truths_covered, but no observable_truth with that ID exists. "
                        f"Valid IDs: {sorted(truth_ids)}",
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Check 3: Truth coverage
# ---------------------------------------------------------------------------


def _check_truth_coverage(plan: Plan) -> list[ValidationError]:
    """Check 3: Every truth is addressed by at least one story AND covered by at least one journey."""
    errors: list[ValidationError] = []

    truth_ids = {t.id for t in plan.observable_truths}

    # Truths addressed by stories
    addressed_by_stories: set[int] = set()
    for story in plan.stories:
        for tid in story.truths_addressed:
            addressed_by_stories.add(tid)

    # Truths covered by journeys
    covered_by_journeys: set[int] = set()
    for journey in plan.user_journeys:
        for tid in journey.truths_covered:
            covered_by_journeys.add(tid)

    truth_map = {t.id: t.statement for t in plan.observable_truths}

    for tid in sorted(truth_ids):
        statement = truth_map.get(tid, "?")
        if tid not in addressed_by_stories:
            errors.append(
                ValidationError(
                    check="truth_coverage",
                    message=f"Observable truth {tid} ('{statement}') is not addressed by "
                    f"any story. Add it to at least one story's truths_addressed.",
                )
            )

        if tid not in covered_by_journeys:
            errors.append(
                ValidationError(
                    check="truth_coverage",
                    message=f"Observable truth {tid} ('{statement}') is not covered by "
                    f"any user journey. Add it to at least one journey's truths_covered.",
                )
            )

    return errors


# ---------------------------------------------------------------------------
# Check 4: Journey coverage
# ---------------------------------------------------------------------------


def _check_journey_coverage(plan: Plan) -> list[ValidationError]:
    """Check 4: Every truth appears in at least one journey's truths_covered."""
    errors: list[ValidationError] = []

    truth_ids = {t.id for t in plan.observable_truths}

    covered_by_journeys: set[int] = set()
    for journey in plan.user_journeys:
        for tid in journey.truths_covered:
            covered_by_journeys.add(tid)

    truth_map = {t.id: t.statement for t in plan.observable_truths}
    orphan_truths = truth_ids - covered_by_journeys
    for tid in sorted(orphan_truths):
        statement = truth_map.get(tid, "?")
        errors.append(
            ValidationError(
                check="journey_coverage",
                message=f"Orphan truth: observable truth {tid} ('{statement}') is asserted "
                f"but never exercised in a connected user journey flow. Add it to at "
                f"least one journey's truths_covered.",
            )
        )

    return errors


# ---------------------------------------------------------------------------
# Check 5: Scope coherence
# ---------------------------------------------------------------------------


def _check_scope_coherence(plan: Plan) -> list[ValidationError]:
    """Check 5: Files in modify scope exist on disk; files in create scope have existing parent dirs."""
    errors: list[ValidationError] = []

    for story in plan.stories:
        # Files in modify must exist on disk
        for fpath in story.scope.modify:
            full_path = PROJECT_ROOT / fpath
            if not full_path.exists():
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{story.story_id}' lists '{fpath}' in scope.modify, "
                        f"but the file does not exist on disk.",
                    )
                )

        # Files in create must have existing parent directories
        for fpath in story.scope.create:
            full_path = PROJECT_ROOT / fpath
            parent = full_path.parent
            if not parent.exists():
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{story.story_id}' lists '{fpath}' in scope.create, "
                        f"but the parent directory "
                        f"'{parent.relative_to(PROJECT_ROOT)}' does not exist.",
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Check 6: Dependency ordering
# ---------------------------------------------------------------------------


def _check_dependency_ordering(plan: Plan) -> list[ValidationError]:
    """Check 6: Stories referencing files from earlier stories appear after them."""
    errors: list[ValidationError] = []

    stories = plan.stories

    # Build a map: file -> index of the story that creates it
    created_by_index: dict[str, int] = {}
    for i, story in enumerate(stories):
        for fpath in story.scope.create:
            created_by_index[fpath] = i

    # Check that stories modifying files created by earlier stories
    # appear after those stories
    for i, story in enumerate(stories):
        for fpath in story.scope.modify:
            if fpath in created_by_index:
                creator_index = created_by_index[fpath]
                if i <= creator_index:
                    creator_sid = stories[creator_index].story_id
                    errors.append(
                        ValidationError(
                            check="dependency_ordering",
                            message=f"Story '{story.story_id}' (index {i}) modifies '{fpath}', "
                            f"which is created by story '{creator_sid}' (index {creator_index}). "
                            f"'{story.story_id}' must appear after '{creator_sid}' in the "
                            f"stories array.",
                        )
                    )

        # Check: if a file is created by two different stories
        for fpath in story.scope.create:
            if fpath in created_by_index and created_by_index[fpath] != i:
                other_index = created_by_index[fpath]
                other_sid = stories[other_index].story_id
                if other_index < i:
                    errors.append(
                        ValidationError(
                            check="dependency_ordering",
                            message=f"File '{fpath}' is created by both story '{other_sid}' "
                            f"(index {other_index}) and story '{story.story_id}' (index {i}). "
                            f"Each file should be created by exactly one story.",
                        )
                    )

    return errors


# ---------------------------------------------------------------------------
# Check 7: Budget sanity
# ---------------------------------------------------------------------------


def _check_budget_sanity(plan: Plan) -> list[ValidationError]:
    """Check 7: Total max_budget_usd is within a reasonable limit."""
    errors: list[ValidationError] = []

    total_budget = sum(story.agent.max_budget_usd for story in plan.stories)

    if total_budget > MAX_TOTAL_BUDGET_USD:
        errors.append(
            ValidationError(
                check="budget_sanity",
                message=f"Total max_budget_usd across all stories is ${total_budget:.2f}, "
                f"which exceeds the sanity limit of ${MAX_TOTAL_BUDGET_USD:.2f}. "
                f"Review story budgets for reasonableness.",
            )
        )

    if total_budget <= 0:
        errors.append(
            ValidationError(
                check="budget_sanity",
                message="Total max_budget_usd is $0.00 or negative. "
                "Every story must have a positive budget.",
            )
        )

    return errors


# ---------------------------------------------------------------------------
# Check 8: Command coverage
# ---------------------------------------------------------------------------


def _check_command_coverage(plan: Plan) -> list[ValidationError]:
    """Check 8: Every checkpoint criterion resolves to a command.

    A criterion resolves if it has an explicit ``command`` field or if
    ``_match_command()`` finds a keyword match. Criteria without a
    mapping produce warnings (not errors) since existing plans may
    lack commands.
    """
    warnings: list[ValidationError] = []

    for cp in plan.validation_checkpoints:
        for check in cp.checks:
            has_explicit = bool(check.command)
            has_keyword = _match_command(check.criterion) is not None

            if not has_explicit and not has_keyword:
                warnings.append(
                    ValidationError(
                        check="command_coverage",
                        message=f"Checkpoint after '{cp.after_story}': criterion "
                        f"'{check.criterion}' has no command field and no keyword "
                        f"match. It will be skipped during validation.",
                    )
                )

    return warnings


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def _check_empty_checkpoints(plan: Plan) -> list[ValidationError]:
    """Check 9: No checkpoint should have an empty checks list.

    An empty checks list means the story has no verification criteria,
    which would silently pass validation without proving anything.
    """
    errors: list[ValidationError] = []

    for cp in plan.validation_checkpoints:
        if not cp.checks:
            errors.append(
                ValidationError(
                    check="empty_checkpoint",
                    message=f"Checkpoint after '{cp.after_story}' has no checks. "
                    f"Every checkpoint must have at least one verification criterion.",
                )
            )

    return errors


def validate_plan(epic_dir: Path) -> ValidationResult:
    """Run 7 deterministic validation checks on plan.json.

    Phase A of the two-phase plan verification system. This is the
    deterministic, $0, instant check. Check 1 (schema conformance) is
    eliminated — Pydantic validation already handles it at parse time.
    Check 8 (command coverage) runs but only produces warnings.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain plan.json.

    Returns:
        ValidationResult with valid=True/False and a list of specific errors.
    """
    plan_json_path = epic_dir / "plan.json"
    if not plan_json_path.is_file():
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    check="file_exists",
                    message=f"plan.json not found at {plan_json_path}. Run plan generation first.",
                )
            ],
        )

    try:
        raw = json.loads(plan_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    check="json_parse",
                    message=f"plan.json is not valid JSON: {exc}",
                )
            ],
        )

    # Validate against Pydantic model (replaces Check 1: schema conformance)
    try:
        plan = Plan.model_validate(raw)
    except Exception as exc:
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    check="schema_conformance",
                    message=f"plan.json failed Pydantic validation: {exc}",
                )
            ],
        )

    # Run checks 2-7 on the validated model
    all_errors: list[ValidationError] = []
    all_errors.extend(_check_referential_integrity(plan))
    all_errors.extend(_check_truth_coverage(plan))
    all_errors.extend(_check_journey_coverage(plan))
    all_errors.extend(_check_scope_coherence(plan))
    all_errors.extend(_check_dependency_ordering(plan))
    all_errors.extend(_check_budget_sanity(plan))
    all_errors.extend(_check_empty_checkpoints(plan))

    # Check 8: Command coverage (warnings only — doesn't fail validation)
    command_warnings = _check_command_coverage(plan)
    for w in command_warnings:
        logger.warning("Check 8 warning: %s", w.message)

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python -m workflow.plan_validator <epic_number>."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <epic_number>", file=sys.stderr)
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(f"Error: epic_number must be an integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(f"Error: Epic directory not found: {epic_dir}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = validate_plan(epic_dir)

    if result.valid:
        print(f"Phase A validation PASSED for epic #{epic_number}")
        sys.exit(0)
    else:
        print(f"Phase A validation FAILED for epic #{epic_number}:")
        for error in result.errors:
            print(f"  {error}")
        print(f"\n{len(result.errors)} error(s) found.")

        # Also print the error messages formatted for planner retry
        print("\nFormatted for planner retry prompt:")
        for msg in result.error_messages():
            print(f"  - {msg}")

        sys.exit(1)


if __name__ == "__main__":
    main()
