"""Phase A: Deterministic plan validation ($0 AI cost).

Validates plan.json against the JSON Schema from Step 1 and checks 7
structural properties that are mechanical and instant to verify. This
runs before Phase B (AI verification) to catch structural errors without
spending any AI tokens.

Reference: Research doc Section 8.4 Decision 8.

Usage:
    python scripts/plan_validator.py <epic_number>
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
SCHEMAS_DIR = PROJECT_ROOT / "scripts" / "schemas"

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
# Schema conformance (Check 1)
# ---------------------------------------------------------------------------


def _load_plan_schema() -> dict:
    """Load plan.schema.json."""
    schema_path = SCHEMAS_DIR / "plan.schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Plan schema not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Check 1: Schema conformance (via jsonschema library)
# ---------------------------------------------------------------------------


def _check_schema_conformance(plan: dict) -> list[ValidationError]:
    """Check 1: plan.json validates against plan.schema.json.

    Uses the jsonschema library for full Draft 2020-12 validation when
    available. Falls back to checking only required top-level fields
    when jsonschema is not installed.
    """
    schema = _load_plan_schema()

    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(schema)
        errors: list[ValidationError] = []
        for error in sorted(validator.iter_errors(plan), key=lambda e: list(e.absolute_path)):
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(
                ValidationError(
                    check="schema_conformance",
                    message=f"{path}: {error.message}",
                )
            )
        return errors

    # Fallback: check required top-level fields only
    errors = []
    for req_field in schema.get("required", []):
        if req_field not in plan:
            errors.append(
                ValidationError(
                    check="schema_conformance",
                    message=f"Missing required top-level field: '{req_field}'",
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Check 2: Referential integrity
# ---------------------------------------------------------------------------


def _check_referential_integrity(plan: dict) -> list[ValidationError]:
    """Check 2: All cross-references are valid.

    - Every truths_addressed ID exists in observable_truths
    - Every checkpoint after_story references a valid story_id
    - Every journey truths_covered ID exists in observable_truths
    """
    errors: list[ValidationError] = []

    truth_ids = {
        t["id"] for t in plan.get("observable_truths", []) if isinstance(t, dict) and "id" in t
    }
    story_ids = {
        s["story_id"] for s in plan.get("stories", []) if isinstance(s, dict) and "story_id" in s
    }

    # truths_addressed in stories
    for story in plan.get("stories", []):
        if not isinstance(story, dict):
            continue
        sid = story.get("story_id", "?")
        for tid in story.get("truths_addressed", []):
            if tid not in truth_ids:
                errors.append(
                    ValidationError(
                        check="referential_integrity",
                        message=f"Story '{sid}' references truth ID {tid} in truths_addressed, "
                        f"but no observable_truth with that ID exists. Valid IDs: {sorted(truth_ids)}",
                    )
                )

    # after_story in validation_checkpoints
    for cp in plan.get("validation_checkpoints", []):
        if not isinstance(cp, dict):
            continue
        after = cp.get("after_story", "?")
        if after not in story_ids:
            errors.append(
                ValidationError(
                    check="referential_integrity",
                    message=f"Checkpoint after_story '{after}' does not match any story_id. "
                    f"Valid story_ids: {sorted(story_ids)}",
                )
            )

    # truths_covered in user_journeys
    for journey in plan.get("user_journeys", []):
        if not isinstance(journey, dict):
            continue
        jid = journey.get("journey_id", "?")
        for tid in journey.get("truths_covered", []):
            if tid not in truth_ids:
                errors.append(
                    ValidationError(
                        check="referential_integrity",
                        message=f"Journey '{jid}' references truth ID {tid} in truths_covered, "
                        f"but no observable_truth with that ID exists. Valid IDs: {sorted(truth_ids)}",
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Check 3: Truth coverage
# ---------------------------------------------------------------------------


def _check_truth_coverage(plan: dict) -> list[ValidationError]:
    """Check 3: Every truth is addressed by at least one story AND covered by at least one journey."""
    errors: list[ValidationError] = []

    truth_ids = {
        t["id"] for t in plan.get("observable_truths", []) if isinstance(t, dict) and "id" in t
    }

    # Truths addressed by stories
    addressed_by_stories: set[int] = set()
    for story in plan.get("stories", []):
        if isinstance(story, dict):
            for tid in story.get("truths_addressed", []):
                addressed_by_stories.add(tid)

    # Truths covered by journeys
    covered_by_journeys: set[int] = set()
    for journey in plan.get("user_journeys", []):
        if isinstance(journey, dict):
            for tid in journey.get("truths_covered", []):
                covered_by_journeys.add(tid)

    for tid in sorted(truth_ids):
        if tid not in addressed_by_stories:
            # Find the truth statement for a helpful error message
            statement = _find_truth_statement(plan, tid)
            errors.append(
                ValidationError(
                    check="truth_coverage",
                    message=f"Observable truth {tid} ('{statement}') is not addressed by any story. "
                    f"Add it to at least one story's truths_addressed.",
                )
            )

        if tid not in covered_by_journeys:
            statement = _find_truth_statement(plan, tid)
            errors.append(
                ValidationError(
                    check="truth_coverage",
                    message=f"Observable truth {tid} ('{statement}') is not covered by any user journey. "
                    f"Add it to at least one journey's truths_covered.",
                )
            )

    return errors


def _find_truth_statement(plan: dict, truth_id: int) -> str:
    """Find the statement text for a given truth ID."""
    for truth in plan.get("observable_truths", []):
        if isinstance(truth, dict) and truth.get("id") == truth_id:
            return truth.get("statement", "?")
    return "?"


# ---------------------------------------------------------------------------
# Check 4: Journey coverage
# ---------------------------------------------------------------------------


def _check_journey_coverage(plan: dict) -> list[ValidationError]:
    """Check 4: Every truth appears in at least one journey's truths_covered.

    This is intentionally redundant with the journey part of Check 3 to
    make the validation explicit as a separate dimension. The plan spec
    lists this as a separate check.
    """
    errors: list[ValidationError] = []

    truth_ids = {
        t["id"] for t in plan.get("observable_truths", []) if isinstance(t, dict) and "id" in t
    }

    covered_by_journeys: set[int] = set()
    for journey in plan.get("user_journeys", []):
        if isinstance(journey, dict):
            for tid in journey.get("truths_covered", []):
                covered_by_journeys.add(tid)

    orphan_truths = truth_ids - covered_by_journeys
    for tid in sorted(orphan_truths):
        statement = _find_truth_statement(plan, tid)
        errors.append(
            ValidationError(
                check="journey_coverage",
                message=f"Orphan truth: observable truth {tid} ('{statement}') is asserted but never "
                f"exercised in a connected user journey flow. Add it to at least one journey's truths_covered.",
            )
        )

    return errors


# ---------------------------------------------------------------------------
# Check 5: Scope coherence
# ---------------------------------------------------------------------------


def _check_scope_coherence(plan: dict) -> list[ValidationError]:
    """Check 5: Files in modify scope exist on disk; files in create scope have existing parent dirs."""
    errors: list[ValidationError] = []

    for story in plan.get("stories", []):
        if not isinstance(story, dict):
            continue
        sid = story.get("story_id", "?")
        scope = story.get("scope", {})
        if not isinstance(scope, dict):
            continue

        # Files in modify must exist on disk
        for fpath in scope.get("modify", []):
            if not isinstance(fpath, str):
                continue
            full_path = PROJECT_ROOT / fpath
            if not full_path.exists():
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{sid}' lists '{fpath}' in scope.modify, "
                        f"but the file does not exist on disk.",
                    )
                )

        # Files in create must have existing parent directories
        for fpath in scope.get("create", []):
            if not isinstance(fpath, str):
                continue
            full_path = PROJECT_ROOT / fpath
            parent = full_path.parent
            if not parent.exists():
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{sid}' lists '{fpath}' in scope.create, "
                        f"but the parent directory '{parent.relative_to(PROJECT_ROOT)}' does not exist.",
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Check 6: Dependency ordering
# ---------------------------------------------------------------------------


def _check_dependency_ordering(plan: dict) -> list[ValidationError]:
    """Check 6: Stories referencing files from earlier stories appear after them.

    If Story B modifies a file that Story A creates, Story B must come
    after Story A in the stories array.
    """
    errors: list[ValidationError] = []

    stories = plan.get("stories", [])
    if not isinstance(stories, list):
        return errors

    # Build a map: file -> index of the story that creates it
    created_by_index: dict[str, int] = {}
    for i, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        scope = story.get("scope", {})
        if not isinstance(scope, dict):
            continue
        for fpath in scope.get("create", []):
            if isinstance(fpath, str):
                created_by_index[fpath] = i

    # Check that stories modifying files created by earlier stories
    # appear after those stories
    for i, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        sid = story.get("story_id", "?")
        scope = story.get("scope", {})
        if not isinstance(scope, dict):
            continue

        for fpath in scope.get("modify", []):
            if not isinstance(fpath, str):
                continue
            if fpath in created_by_index:
                creator_index = created_by_index[fpath]
                if i <= creator_index:
                    creator_story = stories[creator_index]
                    creator_sid = (
                        creator_story.get("story_id", "?")
                        if isinstance(creator_story, dict)
                        else "?"
                    )
                    errors.append(
                        ValidationError(
                            check="dependency_ordering",
                            message=f"Story '{sid}' (index {i}) modifies '{fpath}', "
                            f"which is created by story '{creator_sid}' (index {creator_index}). "
                            f"'{sid}' must appear after '{creator_sid}' in the stories array.",
                        )
                    )

        # Also check: if Story B creates a file already in Story A's create,
        # and Story B references something from Story A's create in its modify
        for fpath in scope.get("create", []):
            if not isinstance(fpath, str):
                continue
            if fpath in created_by_index and created_by_index[fpath] != i:
                other_index = created_by_index[fpath]
                other_story = stories[other_index]
                other_sid = (
                    other_story.get("story_id", "?") if isinstance(other_story, dict) else "?"
                )
                # Only report if the other story comes after (creating same file twice is a plan issue)
                if other_index < i:
                    errors.append(
                        ValidationError(
                            check="dependency_ordering",
                            message=f"File '{fpath}' is created by both story '{other_sid}' (index {other_index}) "
                            f"and story '{sid}' (index {i}). Each file should be created by exactly one story.",
                        )
                    )

    return errors


# ---------------------------------------------------------------------------
# Check 7: Budget sanity
# ---------------------------------------------------------------------------


def _check_budget_sanity(plan: dict) -> list[ValidationError]:
    """Check 7: Total max_budget_usd is within a reasonable limit."""
    errors: list[ValidationError] = []

    total_budget = 0.0
    for story in plan.get("stories", []):
        if not isinstance(story, dict):
            continue
        agent = story.get("agent", {})
        if isinstance(agent, dict):
            budget = agent.get("max_budget_usd", 0)
            if isinstance(budget, int | float):
                total_budget += budget

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
                message="Total max_budget_usd is $0.00 or negative. Every story must have a positive budget.",
            )
        )

    return errors


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def validate_plan(epic_dir: Path) -> ValidationResult:
    """Run all 7 deterministic validation checks on plan.json.

    Phase A of the two-phase plan verification system. This is the
    deterministic, $0, instant check. If this fails, the planner is
    re-invoked with the validation errors before spending AI tokens on
    Phase B.

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
                    message=f"plan.json not found at {plan_json_path}. "
                    "Run plan generation first.",
                )
            ],
        )

    try:
        plan = json.loads(plan_json_path.read_text(encoding="utf-8"))
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

    if not isinstance(plan, dict):
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    check="schema_conformance",
                    message=f"plan.json root must be an object, got {type(plan).__name__}",
                )
            ],
        )

    # Run all 7 checks
    all_errors: list[ValidationError] = []
    all_errors.extend(_check_schema_conformance(plan))
    all_errors.extend(_check_referential_integrity(plan))
    all_errors.extend(_check_truth_coverage(plan))
    all_errors.extend(_check_journey_coverage(plan))
    all_errors.extend(_check_scope_coherence(plan))
    all_errors.extend(_check_dependency_ordering(plan))
    all_errors.extend(_check_budget_sanity(plan))

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python scripts/plan_validator.py <epic_number>."""
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
