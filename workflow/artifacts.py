"""Typed workflow artifacts for epic planning and verification."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from workflow.models import Plan, render_plan_md

VERIFIER_DIMENSIONS: tuple[str, ...] = (
    "journey_completeness",
    "transition_coverage",
    "intent_alignment",
    "gap_detection",
    "validation_sufficiency",
    "gap_sufficiency",
)


@dataclass(frozen=True)
class EpicArtifact:
    """Epic contract loaded from an epic directory."""

    epic_number: int
    body: str

    @classmethod
    def from_epic_dir(cls, epic_dir: Path) -> "EpicArtifact":
        epic_path = epic_dir / "EPIC.md"
        if not epic_path.is_file():
            raise FileNotFoundError(epic_path)

        match = re.match(r"^E(\d+)$", epic_dir.name)
        if not match:
            raise ValueError(f"Cannot extract epic number from directory name: {epic_dir.name}")

        return cls(
            epic_number=int(match.group(1)),
            body=epic_path.read_text(encoding="utf-8"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "epic_number": self.epic_number,
            "body": self.body,
        }

    @property
    def prompt_block(self) -> str:
        return f"<epic>\n{self.body}\n</epic>"


def _compact_plan_payload(plan_json: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "schema_v": plan_json.get("schema_v"),
        "epic_number": plan_json.get("epic_number"),
        "goal": plan_json.get("goal"),
        "observable_truths": plan_json.get("observable_truths", []),
        "user_journeys": plan_json.get("user_journeys", []),
        "validation_checkpoints": plan_json.get("validation_checkpoints", []),
        "stories": [],
    }

    for story in plan_json.get("stories", []):
        compact["stories"].append(
            {
                "story_id": story.get("story_id"),
                "name": story.get("name"),
                "purpose": story.get("purpose"),
                "agent": story.get("agent"),
                "scope": story.get("scope"),
                "acceptance_criteria": story.get("acceptance_criteria", []),
                "truths_addressed": story.get("truths_addressed", []),
                "test_spec": story.get("test_spec"),
            }
        )

    return compact


@dataclass(frozen=True)
class PlanArtifact:
    """Validated plan artifact with deterministic renderers."""

    plan: Plan

    @classmethod
    def from_model(cls, plan: Plan) -> "PlanArtifact":
        return cls(plan=plan)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanArtifact":
        return cls(plan=Plan.model_validate(data))

    @classmethod
    def from_json_text(cls, text: str) -> "PlanArtifact":
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_path(cls, path: Path) -> "PlanArtifact":
        if not path.is_file():
            raise FileNotFoundError(path)
        return cls.from_json_text(path.read_text(encoding="utf-8"))

    @property
    def epic_number(self) -> int:
        return self.plan.epic_number

    def to_dict(self) -> dict[str, Any]:
        return self.plan.model_dump()

    @property
    def json_text(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    @property
    def markdown(self) -> str:
        return render_plan_md(self.plan)

    @property
    def review_payload(self) -> dict[str, Any]:
        return _compact_plan_payload(self.to_dict())

    @property
    def review_json_text(self) -> str:
        return json.dumps(self.review_payload, indent=2, ensure_ascii=False) + "\n"

    def write(self, epic_dir: Path) -> tuple[Path, Path]:
        plan_json_path = epic_dir / "plan.json"
        plan_json_path.write_text(self.json_text, encoding="utf-8")

        plan_md_path = epic_dir / "PLAN.md"
        plan_md_path.write_text(self.markdown, encoding="utf-8")

        return plan_md_path, plan_json_path


@dataclass(frozen=True)
class VerifierFeedbackArtifact:
    """Structured verifier output normalized behind a typed facade."""

    raw_payload: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VerifierFeedbackArtifact":
        if not isinstance(payload, dict):
            raise TypeError(f"Verifier feedback must be a dict, got {type(payload)!r}")
        return cls(raw_payload=payload)

    @property
    def status(self) -> str:
        return str(self.raw_payload.get("status", "unknown"))

    @property
    def summary(self) -> str:
        summary = self.raw_payload.get("summary")
        return "" if summary is None else str(summary)

    @property
    def dimensions(self) -> dict[str, Any]:
        dims = self.raw_payload.get("dimensions")
        if isinstance(dims, dict):
            return dims
        return {
            name: self.raw_payload[name]
            for name in VERIFIER_DIMENSIONS
            if isinstance(self.raw_payload.get(name), dict)
        }

    def dimension(self, name: str) -> dict[str, Any]:
        dim = self.dimensions.get(name, {})
        return dim if isinstance(dim, dict) else {}

    def failed_dimensions(self) -> list[str]:
        failures: list[str] = []
        for name in VERIFIER_DIMENSIONS:
            if self.dimension(name).get("status") == "fail":
                failures.append(name)
        return failures

    def has_extractable_findings(self) -> bool:
        for name in VERIFIER_DIMENSIONS:
            dim = self.dimension(name)
            if dim.get("status") != "fail":
                continue
            findings = dim.get("findings")
            if isinstance(findings, list) and any(
                finding.get("severity") == "must_fix"
                for finding in findings
                if isinstance(finding, dict)
            ):
                return True
            if isinstance(findings, dict) and any(findings.values()):
                return True
            for key in (
                "gaps",
                "uncovered",
                "unaddressed_requirements",
                "scope_creep",
                "weak_checks",
                "missed_gaps",
            ):
                if dim.get(key):
                    return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw_payload)

    @property
    def json_text(self) -> str:
        return json.dumps(self.raw_payload, indent=2, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class RevisionRequestArtifact:
    """Typed input for planner revision prompts."""

    phase: Literal["phase_a", "phase_b"]
    plan: PlanArtifact
    errors: tuple[str, ...] = ()
    epic: EpicArtifact | None = None
    verifier_feedback: VerifierFeedbackArtifact | None = None

    def __post_init__(self) -> None:
        if self.phase == "phase_a":
            if not self.errors:
                raise ValueError("Phase A revision request requires validation errors")
            if self.epic is not None or self.verifier_feedback is not None:
                raise ValueError("Phase A revision request only accepts plan + errors")
            return

        if self.epic is None or self.verifier_feedback is None:
            raise ValueError("Phase B revision request requires epic, plan, and verifier feedback")
        if self.errors:
            raise ValueError("Phase B revision request does not accept validation errors")

    @classmethod
    def for_phase_a(
        cls,
        plan: PlanArtifact,
        errors: list[str],
    ) -> "RevisionRequestArtifact":
        return cls(
            phase="phase_a",
            plan=plan,
            errors=tuple(errors),
        )

    @classmethod
    def for_phase_b(
        cls,
        epic: EpicArtifact,
        plan: PlanArtifact,
        verifier_feedback: VerifierFeedbackArtifact,
    ) -> "RevisionRequestArtifact":
        return cls(
            phase="phase_b",
            epic=epic,
            plan=plan,
            verifier_feedback=verifier_feedback,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "phase": self.phase,
            "plan": self.plan.to_dict(),
        }
        if self.errors:
            data["errors"] = list(self.errors)
        if self.epic is not None:
            data["epic"] = self.epic.to_dict()
        if self.verifier_feedback is not None:
            data["verifier_feedback"] = self.verifier_feedback.to_dict()
        return data
