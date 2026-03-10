"""Phase A: Deterministic plan validation ($0 AI cost).

Validates plan.json against the Pydantic Plan model and runs deterministic
checks that are mechanical and instant to verify. This runs before Phase B
(AI verification) to catch structural errors and contract drift without
spending any AI tokens.

Schema conformance is enforced by Pydantic validation in the plan generator.
Command coverage still runs as a warning-only check.

Reference: Research doc Section 8.4 Decision 8.

Usage:
    python -m workflow.plan_validator <epic_number>
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from workflow.models import Plan
from workflow.validation import _match_command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


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
# Referential integrity
# ---------------------------------------------------------------------------


def _check_referential_integrity(plan: Plan) -> list[ValidationError]:
    """All cross-references must be valid.

    - Every truths_addressed ID exists in observable_truths
    - Every checkpoint after_story references a valid story_id
    - Every journey truths_covered ID exists in observable_truths
    - Every contract decision affected_story references a valid story_id
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

    # affected_stories in contract_decisions
    for decision in plan.contract_decisions:
        for story_id in decision.affected_stories:
            if story_id not in story_ids:
                errors.append(
                    ValidationError(
                        check="referential_integrity",
                        message=(
                            f"Contract decision '{decision.decision_id}' references story_id "
                            f"'{story_id}' in affected_stories, but no story with that ID exists. "
                            f"Valid story_ids: {sorted(story_ids)}"
                        ),
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Truth coverage
# ---------------------------------------------------------------------------


def _check_truth_coverage(plan: Plan) -> list[ValidationError]:
    """Every truth must be addressed by a story and covered by a journey."""
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
# Journey coverage
# ---------------------------------------------------------------------------


def _check_journey_coverage(plan: Plan) -> list[ValidationError]:
    """Every truth must appear in at least one journey's truths_covered."""
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
# Scope coherence
# ---------------------------------------------------------------------------


def _check_scope_coherence(plan: Plan) -> list[ValidationError]:
    """Files in modify scope must exist on disk or in projected state from earlier stories."""
    errors: list[ValidationError] = []

    # Track files and directories that earlier stories will create
    projected_files: set[str] = set()
    projected_dirs: set[str] = set()

    for story in plan.stories:
        # Files in modify must exist on disk OR in projected state from earlier stories
        for fpath in story.scope.modify:
            full_path = PROJECT_ROOT / fpath
            if not full_path.exists() and fpath not in projected_files:
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{story.story_id}' lists '{fpath}' in scope.modify, "
                        f"but the file does not exist on disk and is not created "
                        f"by a prior story.",
                    )
                )

        # Files in create must have existing parent directories (on disk or projected)
        for fpath in story.scope.create:
            full_path = PROJECT_ROOT / fpath
            parent = full_path.parent
            parent_rel = str(parent.relative_to(PROJECT_ROOT))
            if not parent.exists() and parent_rel not in projected_dirs:
                errors.append(
                    ValidationError(
                        check="scope_coherence",
                        message=f"Story '{story.story_id}' lists '{fpath}' in scope.create, "
                        f"but the parent directory "
                        f"'{parent_rel}' does not exist and is not created "
                        f"by a prior story.",
                    )
                )

            # Add this file and all ancestor directories to projected state
            projected_files.add(fpath)
            p = Path(fpath).parent
            while str(p) != ".":
                projected_dirs.add(str(p))
                p = p.parent

    return errors


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------


def _check_dependency_ordering(plan: Plan) -> list[ValidationError]:
    """Stories referencing files from earlier stories must appear after them."""
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
# Command coverage
# ---------------------------------------------------------------------------


def _check_command_coverage(plan: Plan) -> list[ValidationError]:
    """Every checkpoint criterion should resolve to a command.

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
# Contract fidelity
# ---------------------------------------------------------------------------

_ROUTE_SURFACE_PATTERN = re.compile(r"(?<![A-Za-z0-9])/(?:[^\s`'\"<>()\[\],;]+|<[^>\n/]+>|{[^}\n/]+})+")
_NON_ROUTE_SUFFIXES = (
    ".py",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
)


def _normalize_route_surface(value: str) -> str | None:
    cleaned = value.strip().rstrip(".,:;!?)]}'\"")
    if not cleaned.startswith("/") or cleaned == "/":
        return None
    leaf = cleaned.rstrip("/").split("/")[-1]
    if any(leaf.endswith(suffix) for suffix in _NON_ROUTE_SUFFIXES):
        return None
    return cleaned.rstrip("/")


def _extract_route_like_surfaces(epic_body: str) -> list[str]:
    """Extract pragmatic route-like surfaces from EPIC.md text."""
    seen: set[str] = set()
    routes: list[str] = []
    for raw in _ROUTE_SURFACE_PATTERN.findall(epic_body):
        normalized = _normalize_route_surface(raw)
        if normalized is None:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        routes.append(normalized)
    return routes


def _plan_contract_surface_text(plan: Plan) -> str:
    parts: list[str] = []
    parts.extend(truth.statement for truth in plan.observable_truths)
    for journey in plan.user_journeys:
        parts.append(journey.narrative)
        parts.append(journey.entry_point)
        for transition in journey.critical_transitions:
            parts.extend([transition.source, transition.to, transition.mechanism])
    for story in plan.stories:
        parts.extend(story.acceptance_criteria)
    for decision in plan.contract_decisions:
        parts.extend([decision.epic_contract, decision.repo_convention])
        if decision.bridge:
            parts.append(decision.bridge)
    return "\n".join(parts).lower()


def _check_contract_fidelity(plan: Plan, epic_body: str) -> list[ValidationError]:
    """Epic route surfaces must survive planning or be recorded explicitly."""
    errors: list[ValidationError] = []
    route_surfaces = _extract_route_like_surfaces(epic_body)
    if not route_surfaces:
        return errors

    plan_text = _plan_contract_surface_text(plan)
    for route in route_surfaces:
        if route.lower() in plan_text:
            continue
        errors.append(
            ValidationError(
                check="contract_fidelity",
                message=(
                    f"Epic route '{route}' disappears from the plan. Preserve it in the plan text "
                    "or record an explicit contract_decision that names the epic contract and any bridge."
                ),
            )
        )
    return errors


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def _check_empty_checkpoints(plan: Plan) -> list[ValidationError]:
    """No checkpoint should have an empty checks list.

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


def _check_acceptance_criteria(plan: Plan) -> list[ValidationError]:
    """Every story must have non-empty acceptance_criteria.

    An empty acceptance_criteria list means the agent has no verifiable
    definition of done, making the story unvalidatable.
    """
    errors: list[ValidationError] = []

    for story in plan.stories:
        if not story.acceptance_criteria:
            errors.append(
                ValidationError(
                    check="acceptance_criteria",
                    message=f"Story '{story.story_id}' has empty acceptance_criteria. "
                    f"Every story must have at least one acceptance criterion.",
                )
            )

    return errors


def _check_story_enrichment(plan: Plan) -> list[ValidationError]:
    """Every story must have non-empty enrichment fields.

    - architectural_context: required non-empty on ALL stories.
    - navigation_hints: required non-empty on ALL stories.
    """
    errors: list[ValidationError] = []

    for story in plan.stories:
        if not story.architectural_context:
            errors.append(
                ValidationError(
                    check="story_enrichment",
                    message=f"Story '{story.story_id}' has empty architectural_context. "
                    f"Every story must have at least one architectural context item.",
                )
            )
        if not story.navigation_hints:
            errors.append(
                ValidationError(
                    check="story_enrichment",
                    message=f"Story '{story.story_id}' has empty navigation_hints. "
                    f"Every story must have at least one navigation hint.",
                )
            )

    return errors


def _check_checkpoint_coverage(plan: Plan) -> list[ValidationError]:
    """Every story must have a validation checkpoint.

    A story without a checkpoint will fail at runtime with
    'No validation checkpoint defined for story'. Catch this at
    plan validation time instead.
    """
    errors: list[ValidationError] = []
    checkpoint_stories = {cp.after_story for cp in plan.validation_checkpoints}

    for story in plan.stories:
        if story.story_id not in checkpoint_stories:
            errors.append(
                ValidationError(
                    check="missing_checkpoint",
                    message=f"Story '{story.story_id}' has no validation checkpoint. "
                    f"Every story must have a validation_checkpoints entry.",
                )
            )

    return errors


# Valid assertion types for test_spec
_VALID_ASSERTION_TYPES = {"http_status", "dom_element", "dom_absent", "db_state", "api_response"}

# Valid test types for test_spec
_VALID_TEST_TYPES = {"integration", "e2e"}

# Known fixture names (base names without arguments)
_KNOWN_FIXTURES = {
    "make_user",
    "make_di_track",
    "make_shootout",
    "make_gear",
    "make_signal_chain",
    "make_user_gear",
    "test_user",
    "test_di_track",
    "test_gear",
    "test_shootout",
    "test_signal_chain",
    "authenticated_client",
    "db_session",
    "session",
    "seeded_db_session",
}


def _check_test_specs(plan: Plan) -> list[ValidationError]:
    """Check test_spec fields on stories.

    - Warns (not errors) if a story is missing test_spec.
    - Errors if test_type is invalid.
    - Errors if fixtures reference unknown fixture names.
    - Errors if assertions have invalid type values.
    """
    import re

    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    for story in plan.stories:
        if story.test_spec is None:
            warnings.append(
                ValidationError(
                    check="test_spec",
                    message=f"Story '{story.story_id}' has no test_spec. "
                    f"Consider adding a test_spec for automated validation.",
                )
            )
            continue

        spec = story.test_spec

        # Validate test_type
        if spec.test_type not in _VALID_TEST_TYPES:
            errors.append(
                ValidationError(
                    check="test_spec",
                    message=f"Story '{story.story_id}' test_spec.test_type is "
                    f"'{spec.test_type}', must be one of: {sorted(_VALID_TEST_TYPES)}.",
                )
            )

        # Validate fixture names (strip parenthesised arguments)
        for fixture in spec.fixtures:
            base_name = re.split(r"[(\s]", fixture)[0]
            if base_name not in _KNOWN_FIXTURES:
                errors.append(
                    ValidationError(
                        check="test_spec",
                        message=f"Story '{story.story_id}' test_spec.fixtures references "
                        f"unknown fixture '{base_name}'. Known fixtures: "
                        f"{sorted(_KNOWN_FIXTURES)}.",
                    )
                )

        # Validate assertion types
        for i, assertion in enumerate(spec.assertions):
            if assertion.type not in _VALID_ASSERTION_TYPES:
                errors.append(
                    ValidationError(
                        check="test_spec",
                        message=f"Story '{story.story_id}' test_spec.assertions[{i}].type is "
                        f"'{assertion.type}', must be one of: {sorted(_VALID_ASSERTION_TYPES)}.",
                    )
                )

    # Log warnings but don't include them in errors
    for w in warnings:
        logger.warning("Test spec warning: %s", w.message)

    return errors


def validate_plan(epic_dir: Path) -> ValidationResult:
    """Run deterministic Phase A validation checks on plan.json.

    Phase A of the two-phase plan verification system. This is the
    deterministic, $0, instant check. Schema conformance is handled by
    Pydantic at parse time. Command coverage runs but only produces warnings.

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

    # Validate against the Pydantic model first.
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

    # Run checks 2-11 on the validated model
    all_errors: list[ValidationError] = []
    all_errors.extend(_check_referential_integrity(plan))
    all_errors.extend(_check_truth_coverage(plan))
    all_errors.extend(_check_journey_coverage(plan))
    all_errors.extend(_check_scope_coherence(plan))
    all_errors.extend(_check_dependency_ordering(plan))
    epic_path = epic_dir / "EPIC.md"
    if epic_path.is_file():
        all_errors.extend(
            _check_contract_fidelity(
                plan,
                epic_path.read_text(encoding="utf-8"),
            )
        )
    else:
        logger.warning("Skipping contract_fidelity check because EPIC.md is missing at %s", epic_path)
    all_errors.extend(_check_empty_checkpoints(plan))
    all_errors.extend(_check_checkpoint_coverage(plan))
    all_errors.extend(_check_acceptance_criteria(plan))
    all_errors.extend(_check_story_enrichment(plan))
    all_errors.extend(_check_test_specs(plan))

    # Command coverage is warning-only; it does not fail validation.
    command_warnings = _check_command_coverage(plan)
    for w in command_warnings:
        logger.warning("Command coverage warning: %s", w.message)

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
