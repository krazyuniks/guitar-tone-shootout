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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

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


def _check_type(value: object, expected_type: str, path: str) -> list[str]:
    """Check that a value matches the expected JSON Schema type. Returns error messages."""
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    expected = type_map.get(expected_type)
    if expected is None:
        return []
    if not isinstance(value, expected):
        return [f"{path}: expected type '{expected_type}', got '{type(value).__name__}'"]
    # Integer check: JSON Schema 'integer' means no floats
    if expected_type == "integer" and isinstance(value, float):
        return [f"{path}: expected integer, got float"]
    return []


def _validate_against_schema(plan: dict, schema: dict) -> list[str]:
    """Validate plan.json against plan.schema.json.

    This is a focused validator that checks the specific plan schema structure
    rather than a general-purpose JSON Schema validator. It verifies required
    fields, types, enum values, and constraints defined in the schema.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []

    # Load definitions
    defs = schema.get("$defs", {})

    # Top-level required fields
    for req_field in schema.get("required", []):
        if req_field not in plan:
            errors.append(f"Missing required top-level field: '{req_field}'")

    # schema_v must be 1
    if "schema_v" in plan:
        if plan["schema_v"] != 1:
            errors.append(f"schema_v must be 1, got {plan['schema_v']}")
        errors.extend(_check_type(plan["schema_v"], "integer", "schema_v"))

    # epic_number must be a positive integer
    if "epic_number" in plan:
        errors.extend(_check_type(plan["epic_number"], "integer", "epic_number"))
        if isinstance(plan["epic_number"], int) and plan["epic_number"] < 1:
            errors.append("epic_number must be >= 1")

    # goal must be a non-empty string
    if "goal" in plan:
        errors.extend(_check_type(plan["goal"], "string", "goal"))
        if isinstance(plan["goal"], str) and not plan["goal"].strip():
            errors.append("goal must be a non-empty string")

    # observable_truths
    if "observable_truths" in plan:
        errors.extend(_check_type(plan["observable_truths"], "array", "observable_truths"))
        if isinstance(plan["observable_truths"], list):
            if len(plan["observable_truths"]) < 1:
                errors.append("observable_truths must have at least 1 item")
            for i, truth in enumerate(plan["observable_truths"]):
                prefix = f"observable_truths[{i}]"
                errors.extend(_check_type(truth, "object", prefix))
                if isinstance(truth, dict):
                    for req in ["id", "statement"]:
                        if req not in truth:
                            errors.append(f"{prefix}: missing required field '{req}'")
                    if "id" in truth:
                        errors.extend(_check_type(truth["id"], "integer", f"{prefix}.id"))
                        if isinstance(truth["id"], int) and truth["id"] < 1:
                            errors.append(f"{prefix}.id must be >= 1")
                    if "statement" in truth:
                        errors.extend(
                            _check_type(truth["statement"], "string", f"{prefix}.statement")
                        )
                        if isinstance(truth["statement"], str) and not truth["statement"].strip():
                            errors.append(f"{prefix}.statement must be non-empty")

    # user_journeys
    if "user_journeys" in plan:
        errors.extend(_check_type(plan["user_journeys"], "array", "user_journeys"))
        if isinstance(plan["user_journeys"], list):
            if len(plan["user_journeys"]) < 1:
                errors.append("user_journeys must have at least 1 item")
            for i, journey in enumerate(plan["user_journeys"]):
                prefix = f"user_journeys[{i}]"
                errors.extend(_validate_journey(journey, prefix, defs))

    # stories
    if "stories" in plan:
        errors.extend(_check_type(plan["stories"], "array", "stories"))
        if isinstance(plan["stories"], list):
            if len(plan["stories"]) < 1:
                errors.append("stories must have at least 1 item")
            for i, story in enumerate(plan["stories"]):
                prefix = f"stories[{i}]"
                errors.extend(_validate_story(story, prefix, defs))

    # validation_checkpoints
    if "validation_checkpoints" in plan:
        errors.extend(
            _check_type(plan["validation_checkpoints"], "array", "validation_checkpoints")
        )
        if isinstance(plan["validation_checkpoints"], list):
            for i, cp in enumerate(plan["validation_checkpoints"]):
                prefix = f"validation_checkpoints[{i}]"
                errors.extend(_validate_checkpoint(cp, prefix, defs))

    # Check for unexpected top-level fields
    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}).keys())
        for key in plan:
            if key not in allowed:
                errors.append(f"Unexpected top-level field: '{key}'")

    return errors


def _validate_journey(journey: object, prefix: str, defs: dict) -> list[str]:
    """Validate a user_journey object."""
    errors: list[str] = []
    errors.extend(_check_type(journey, "object", prefix))
    if not isinstance(journey, dict):
        return errors

    required = [
        "journey_id",
        "persona",
        "narrative",
        "truths_covered",
        "entry_point",
        "critical_transitions",
    ]
    for req in required:
        if req not in journey:
            errors.append(f"{prefix}: missing required field '{req}'")

    if "journey_id" in journey:
        errors.extend(_check_type(journey["journey_id"], "string", f"{prefix}.journey_id"))
        if isinstance(journey["journey_id"], str) and not re.match(
            r"^J[0-9]+$", journey["journey_id"]
        ):
            errors.append(
                f"{prefix}.journey_id must match pattern ^J[0-9]+$ (got '{journey['journey_id']}')"
            )

    for str_field in ["persona", "narrative", "entry_point"]:
        if str_field in journey:
            errors.extend(_check_type(journey[str_field], "string", f"{prefix}.{str_field}"))
            if isinstance(journey[str_field], str) and not journey[str_field].strip():
                errors.append(f"{prefix}.{str_field} must be non-empty")

    if "truths_covered" in journey:
        errors.extend(_check_type(journey["truths_covered"], "array", f"{prefix}.truths_covered"))
        if isinstance(journey["truths_covered"], list):
            if len(journey["truths_covered"]) < 1:
                errors.append(f"{prefix}.truths_covered must have at least 1 item")
            for j, tid in enumerate(journey["truths_covered"]):
                errors.extend(_check_type(tid, "integer", f"{prefix}.truths_covered[{j}]"))
                if isinstance(tid, int) and tid < 1:
                    errors.append(f"{prefix}.truths_covered[{j}] must be >= 1")

    if "critical_transitions" in journey:
        errors.extend(
            _check_type(journey["critical_transitions"], "array", f"{prefix}.critical_transitions")
        )
        if isinstance(journey["critical_transitions"], list):
            if len(journey["critical_transitions"]) < 1:
                errors.append(f"{prefix}.critical_transitions must have at least 1 item")
            for j, ct in enumerate(journey["critical_transitions"]):
                ct_prefix = f"{prefix}.critical_transitions[{j}]"
                errors.extend(_check_type(ct, "object", ct_prefix))
                if isinstance(ct, dict):
                    for req in ["from", "to", "mechanism"]:
                        if req not in ct:
                            errors.append(f"{ct_prefix}: missing required field '{req}'")
                        elif not isinstance(ct[req], str) or not ct[req].strip():
                            errors.append(f"{ct_prefix}.{req} must be a non-empty string")

    return errors


def _validate_story(story: object, prefix: str, defs: dict) -> list[str]:
    """Validate a story object."""
    errors: list[str] = []
    errors.extend(_check_type(story, "object", prefix))
    if not isinstance(story, dict):
        return errors

    required = [
        "story_id",
        "name",
        "purpose",
        "agent",
        "scope",
        "implementation_notes",
        "truths_addressed",
    ]
    for req in required:
        if req not in story:
            errors.append(f"{prefix}: missing required field '{req}'")

    if "story_id" in story:
        errors.extend(_check_type(story["story_id"], "string", f"{prefix}.story_id"))
        if isinstance(story["story_id"], str) and not re.match(
            r"^[a-z0-9][a-z0-9-]*$", story["story_id"]
        ):
            errors.append(
                f"{prefix}.story_id must match pattern ^[a-z0-9][a-z0-9-]*$ (got '{story['story_id']}')"
            )

    for str_field in ["name", "purpose"]:
        if str_field in story:
            errors.extend(_check_type(story[str_field], "string", f"{prefix}.{str_field}"))
            if isinstance(story[str_field], str) and not story[str_field].strip():
                errors.append(f"{prefix}.{str_field} must be non-empty")

    if "state_assumption" in story:
        valid_states = ["cumulative", "clean"]
        if story["state_assumption"] not in valid_states:
            errors.append(
                f"{prefix}.state_assumption must be one of {valid_states}, got '{story['state_assumption']}'"
            )

    if "agent" in story:
        errors.extend(_validate_agent_config(story["agent"], f"{prefix}.agent"))

    if "scope" in story:
        errors.extend(_validate_scope(story["scope"], f"{prefix}.scope"))

    if "implementation_notes" in story:
        errors.extend(
            _check_type(story["implementation_notes"], "array", f"{prefix}.implementation_notes")
        )
        if isinstance(story["implementation_notes"], list):
            for j, note in enumerate(story["implementation_notes"]):
                errors.extend(_check_type(note, "string", f"{prefix}.implementation_notes[{j}]"))

    if "truths_addressed" in story:
        errors.extend(_check_type(story["truths_addressed"], "array", f"{prefix}.truths_addressed"))
        if isinstance(story["truths_addressed"], list):
            if len(story["truths_addressed"]) < 1:
                errors.append(f"{prefix}.truths_addressed must have at least 1 item")
            for j, tid in enumerate(story["truths_addressed"]):
                errors.extend(_check_type(tid, "integer", f"{prefix}.truths_addressed[{j}]"))
                if isinstance(tid, int) and tid < 1:
                    errors.append(f"{prefix}.truths_addressed[{j}] must be >= 1")

    return errors


def _validate_agent_config(agent: object, prefix: str) -> list[str]:
    """Validate an agent_config object."""
    errors: list[str] = []
    errors.extend(_check_type(agent, "object", prefix))
    if not isinstance(agent, dict):
        return errors

    required = ["model", "skills", "tools", "mcp", "max_turns", "max_budget_usd"]
    for req in required:
        if req not in agent:
            errors.append(f"{prefix}: missing required field '{req}'")

    if "model" in agent:
        valid_models = ["opus", "sonnet", "haiku"]
        if agent["model"] not in valid_models:
            errors.append(f"{prefix}.model must be one of {valid_models}, got '{agent['model']}'")

    for arr_field in ["skills", "tools", "mcp"]:
        if arr_field in agent:
            errors.extend(_check_type(agent[arr_field], "array", f"{prefix}.{arr_field}"))
            if isinstance(agent[arr_field], list):
                for j, item in enumerate(agent[arr_field]):
                    errors.extend(_check_type(item, "string", f"{prefix}.{arr_field}[{j}]"))

    if "max_turns" in agent:
        errors.extend(_check_type(agent["max_turns"], "integer", f"{prefix}.max_turns"))
        if isinstance(agent["max_turns"], int) and agent["max_turns"] < 1:
            errors.append(f"{prefix}.max_turns must be >= 1")

    if "max_budget_usd" in agent:
        if not isinstance(agent["max_budget_usd"], int | float):
            errors.append(
                f"{prefix}.max_budget_usd: expected number, got '{type(agent['max_budget_usd']).__name__}'"
            )
        elif agent["max_budget_usd"] <= 0:
            errors.append(f"{prefix}.max_budget_usd must be > 0")

    return errors


def _validate_scope(scope: object, prefix: str) -> list[str]:
    """Validate a scope object."""
    errors: list[str] = []
    errors.extend(_check_type(scope, "object", prefix))
    if not isinstance(scope, dict):
        return errors

    for req in ["create", "modify"]:
        if req not in scope:
            errors.append(f"{prefix}: missing required field '{req}'")

    for arr_field in ["create", "modify"]:
        if arr_field in scope:
            errors.extend(_check_type(scope[arr_field], "array", f"{prefix}.{arr_field}"))
            if isinstance(scope[arr_field], list):
                for j, item in enumerate(scope[arr_field]):
                    errors.extend(_check_type(item, "string", f"{prefix}.{arr_field}[{j}]"))

    return errors


def _validate_checkpoint(cp: object, prefix: str, defs: dict) -> list[str]:
    """Validate a validation_checkpoint object."""
    errors: list[str] = []
    errors.extend(_check_type(cp, "object", prefix))
    if not isinstance(cp, dict):
        return errors

    required = ["after_story", "check_type", "checks"]
    for req in required:
        if req not in cp:
            errors.append(f"{prefix}: missing required field '{req}'")

    if "after_story" in cp:
        errors.extend(_check_type(cp["after_story"], "string", f"{prefix}.after_story"))
        if isinstance(cp["after_story"], str) and not cp["after_story"].strip():
            errors.append(f"{prefix}.after_story must be non-empty")

    if "check_type" in cp:
        valid_types = [
            "http",
            "http+dom",
            "browser+db",
            "api+response",
            "process",
            "screenshot",
            "regression",
            "quality",
        ]
        if cp["check_type"] not in valid_types:
            errors.append(
                f"{prefix}.check_type must be one of {valid_types}, got '{cp['check_type']}'"
            )

    if "checks" in cp:
        errors.extend(_check_type(cp["checks"], "array", f"{prefix}.checks"))
        if isinstance(cp["checks"], list):
            if len(cp["checks"]) < 1:
                errors.append(f"{prefix}.checks must have at least 1 item")
            for j, check in enumerate(cp["checks"]):
                check_prefix = f"{prefix}.checks[{j}]"
                errors.extend(_check_type(check, "object", check_prefix))
                if isinstance(check, dict):
                    for req in ["criterion", "evidence_fields"]:
                        if req not in check:
                            errors.append(f"{check_prefix}: missing required field '{req}'")
                    if "criterion" in check:
                        errors.extend(
                            _check_type(check["criterion"], "string", f"{check_prefix}.criterion")
                        )
                        if isinstance(check["criterion"], str) and not check["criterion"].strip():
                            errors.append(f"{check_prefix}.criterion must be non-empty")
                    if "evidence_fields" in check:
                        errors.extend(
                            _check_type(
                                check["evidence_fields"], "array", f"{check_prefix}.evidence_fields"
                            )
                        )
                        if isinstance(check["evidence_fields"], list):
                            if len(check["evidence_fields"]) < 1:
                                errors.append(
                                    f"{check_prefix}.evidence_fields must have at least 1 item"
                                )
                            for k, ef in enumerate(check["evidence_fields"]):
                                errors.extend(
                                    _check_type(
                                        ef, "string", f"{check_prefix}.evidence_fields[{k}]"
                                    )
                                )

    return errors


# ---------------------------------------------------------------------------
# Check 1: Schema conformance
# ---------------------------------------------------------------------------


def _check_schema_conformance(plan: dict) -> list[ValidationError]:
    """Check 1: plan.json validates against plan.schema.json."""
    schema = _load_plan_schema()
    raw_errors = _validate_against_schema(plan, schema)
    return [ValidationError(check="schema_conformance", message=msg) for msg in raw_errors]


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
