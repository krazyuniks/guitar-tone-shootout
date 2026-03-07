"""Typed workflow artifacts for epic planning, verification, and orchestration."""

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

RUN_EVENT_SCHEMA_VERSION = 2


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


@dataclass(frozen=True)
class DispatchArtifact:
    """Serialized lifecycle entry for one dispatch invocation."""

    ts: str
    run_id: str
    dispatch_id: str
    status: Literal["started", "completed"]
    role: str
    model: str
    prompt_hash: str
    prompt_tokens: int
    prompt_file: str
    response_file: str
    conversation_file: str
    response_tokens: int | None = None
    turns: int | None = None
    success: bool | None = None
    exit_code: int | None = None
    duration_ms: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DispatchArtifact":
        return cls(
            ts=str(payload["ts"]),
            run_id=str(payload["run_id"]),
            dispatch_id=str(payload["dispatch_id"]),
            status=str(payload["status"]),
            role=str(payload["role"]),
            model=str(payload["model"]),
            prompt_hash=str(payload["prompt_hash"]),
            prompt_tokens=int(payload["prompt_tokens"]),
            prompt_file=str(payload["prompt_file"]),
            response_file=str(payload["response_file"]),
            conversation_file=str(payload["conversation_file"]),
            response_tokens=(
                int(payload["response_tokens"])
                if payload.get("response_tokens") is not None
                else None
            ),
            turns=int(payload["turns"]) if payload.get("turns") is not None else None,
            success=payload.get("success"),
            exit_code=int(payload["exit_code"]) if payload.get("exit_code") is not None else None,
            duration_ms=(
                int(payload["duration_ms"]) if payload.get("duration_ms") is not None else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ts": self.ts,
            "run_id": self.run_id,
            "dispatch_id": self.dispatch_id,
            "status": self.status,
            "role": self.role,
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "prompt_tokens": self.prompt_tokens,
            "prompt_file": self.prompt_file,
            "response_file": self.response_file,
            "conversation_file": self.conversation_file,
        }
        optional_fields = {
            "response_tokens": self.response_tokens,
            "turns": self.turns,
            "success": self.success,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }
        payload.update({key: value for key, value in optional_fields.items() if value is not None})
        return payload


@dataclass(frozen=True)
class DispatchResultArtifact:
    """Typed result boundary returned by workflow.dispatch."""

    success: bool
    output: str
    structured_output: dict[str, Any] | None = None
    exit_code: int = 0
    turns: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DispatchResultArtifact":
        structured_output = payload.get("structured_output")
        if structured_output is not None and not isinstance(structured_output, dict):
            raise TypeError("structured_output must be a dict when present")

        return cls(
            success=bool(payload["success"]),
            output=str(payload["output"]),
            structured_output=structured_output,
            exit_code=int(payload.get("exit_code", 0)),
            turns=int(payload["turns"]) if payload.get("turns") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "output": self.output,
            "exit_code": self.exit_code,
        }
        if self.structured_output is not None:
            payload["structured_output"] = self.structured_output
        if self.turns is not None:
            payload["turns"] = self.turns
        return payload


@dataclass(frozen=True)
class TestReviewChecklistItemArtifact:
    """One binary checklist item from a test reviewer response."""

    __test__ = False

    item: str
    passed: bool
    note: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TestReviewChecklistItemArtifact":
        return cls(
            item=str(payload["item"]),
            passed=bool(payload["passed"]),
            note=str(payload["note"]) if payload.get("note") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "item": self.item,
            "passed": self.passed,
        }
        if self.note is not None:
            payload["note"] = self.note
        return payload


@dataclass(frozen=True)
class TestReviewArtifact:
    """Typed review output for workflow.test_generator."""

    __test__ = False

    verdict: Literal["pass", "fail"]
    checklist: tuple[TestReviewChecklistItemArtifact, ...]
    suggestions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TestReviewArtifact":
        verdict = str(payload["verdict"])
        if verdict not in {"pass", "fail"}:
            raise ValueError(f"Unsupported test review verdict: {verdict}")

        checklist_payload = payload.get("checklist", [])
        if not isinstance(checklist_payload, list):
            raise TypeError("checklist must be a list")

        suggestions_payload = payload.get("suggestions", [])
        if not isinstance(suggestions_payload, list):
            raise TypeError("suggestions must be a list")
        if any(not isinstance(item, dict) for item in checklist_payload):
            raise TypeError("checklist items must be dicts")

        return cls(
            verdict=verdict,
            checklist=tuple(
                TestReviewChecklistItemArtifact.from_dict(item)
                for item in checklist_payload
            ),
            suggestions=tuple(str(item) for item in suggestions_payload),
        )

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "checklist": [item.to_dict() for item in self.checklist],
            "suggestions": list(self.suggestions),
        }


@dataclass(frozen=True)
class CritiqueFindingArtifact:
    """One normalized critique finding."""

    raw_payload: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CritiqueFindingArtifact":
        if not isinstance(payload, dict):
            raise TypeError(f"Critique finding must be a dict, got {type(payload)!r}")
        return cls(raw_payload=dict(payload))

    @property
    def severity(self) -> str:
        severity = self.raw_payload.get("severity")
        return "" if severity is None else str(severity)

    @property
    def issue(self) -> str:
        issue = self.raw_payload.get("issue")
        return "" if issue is None else str(issue)

    @property
    def file(self) -> str:
        file_ref = self.raw_payload.get("file")
        return "" if file_ref is None else str(file_ref)

    @property
    def line(self) -> int | None:
        line = self.raw_payload.get("line")
        if line is None or line == "":
            return None
        return int(line)

    @property
    def summary_text(self) -> str:
        location = self.location
        if location and self.issue:
            return f"{location} - {self.issue}"
        return self.issue or location or "Unspecified critique finding"

    @property
    def location(self) -> str:
        if not self.file:
            return ""
        if self.line is None:
            return self.file
        return f"{self.file}:{self.line}"

    @property
    def advisory_text(self) -> str:
        severity = self.severity or "?"
        return f"[{severity}] {self.issue or self.summary_text}"

    @property
    def markdown_text(self) -> str:
        severity = self.severity or "?"
        location = self.location or "?"
        return f"- **[{severity}]** `{location}` — {self.issue or self.summary_text}"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw_payload)


@dataclass(frozen=True)
class CritiqueRunArtifact:
    """Typed critique result reconstructed from model output or JSONL events."""

    level: Literal["story", "epic"]
    status: Literal["pass", "fail"]
    critique_type: str
    critique_model: str
    findings: tuple[CritiqueFindingArtifact, ...] = ()
    summary: str = ""
    story_id: str | None = None
    attempt: int | None = None
    turns: int | None = None
    raw_response: str = ""
    error: str = ""
    logged_findings_count: int | None = None
    source_event: str | None = None

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        level: Literal["story", "epic"],
        critique_type: str | None = None,
        critique_model: str = "",
        story_id: str | None = None,
        attempt: int | None = None,
        turns: int | None = None,
        raw_response: str = "",
    ) -> "CritiqueRunArtifact":
        if not isinstance(payload, dict):
            raise TypeError(f"Critique payload must be a dict, got {type(payload)!r}")

        status = str(payload["status"])
        if status not in {"pass", "fail"}:
            raise ValueError(f"Unsupported critique status: {status}")

        findings_payload = payload.get("findings", [])
        if not isinstance(findings_payload, list):
            raise TypeError("Critique findings must be a list")
        if any(not isinstance(item, dict) for item in findings_payload):
            raise TypeError("Critique findings must contain dict entries")

        summary = payload.get("summary")
        return cls(
            level=level,
            status=status,
            critique_type=critique_type or level,
            critique_model=critique_model,
            findings=tuple(CritiqueFindingArtifact.from_dict(item) for item in findings_payload),
            summary="" if summary is None else str(summary),
            story_id=story_id,
            attempt=attempt,
            turns=turns,
            raw_response=raw_response,
        )

    @classmethod
    def for_error(
        cls,
        *,
        level: Literal["story", "epic"],
        critique_type: str | None = None,
        critique_model: str,
        error: str,
        story_id: str | None = None,
        attempt: int | None = None,
        turns: int | None = None,
        raw_response: str = "",
    ) -> "CritiqueRunArtifact":
        return cls(
            level=level,
            status="fail",
            critique_type=critique_type or level,
            critique_model=critique_model,
            story_id=story_id,
            attempt=attempt,
            turns=turns,
            raw_response=raw_response,
            error=error,
            logged_findings_count=0,
            source_event="critique_failed" if level == "story" else "epic_critique_fail",
        )

    @classmethod
    def from_event(
        cls,
        event: dict[str, Any] | "RunEventArtifact",
    ) -> "CritiqueRunArtifact":
        if isinstance(event, RunEventArtifact):
            event_artifact = event
        else:
            event_artifact = RunEventArtifact(
                schema_v=int(event.get("schema_v", RUN_EVENT_SCHEMA_VERSION)),
                run_id=str(event.get("run_id", "")),
                ts=str(event.get("ts", "")),
                event=str(event["event"]),
                data={
                    key: value
                    for key, value in event.items()
                    if key not in {"schema_v", "run_id", "ts", "event"}
                },
            )
        event_name = event_artifact.event
        valid_events = {
            "critique_pass",
            "critique_fail",
            "critique_failed",
            "epic_critique_pass",
            "epic_critique_fail",
        }
        if event_name not in valid_events:
            raise ValueError(f"Cannot build CritiqueRunArtifact from event {event_name}")

        level: Literal["story", "epic"] = "epic" if event_name.startswith("epic_") else "story"
        findings_payload = event_artifact.get("findings", [])
        if not isinstance(findings_payload, list):
            raise TypeError("Critique findings must be a list")
        if any(not isinstance(item, dict) for item in findings_payload):
            raise TypeError("Critique findings must contain dict entries")

        logged_findings_count = event_artifact.get("findings_count")
        return cls(
            level=level,
            status="pass" if event_name.endswith("_pass") else "fail",
            critique_type=str(event_artifact.get("critique_type", level)),
            critique_model=str(event_artifact.get("critique_model", "")),
            findings=tuple(CritiqueFindingArtifact.from_dict(item) for item in findings_payload),
            summary=str(event_artifact.get("summary", "")),
            story_id=(
                str(event_artifact.get("story_id"))
                if event_artifact.get("story_id") is not None
                else None
            ),
            attempt=(
                int(event_artifact.get("attempt"))
                if event_artifact.get("attempt") is not None
                else None
            ),
            turns=(
                int(event_artifact.get("turns"))
                if event_artifact.get("turns") is not None
                else None
            ),
            raw_response=str(event_artifact.get("raw_response", "")),
            error=str(event_artifact.get("error", "")),
            logged_findings_count=(
                int(logged_findings_count) if logged_findings_count is not None else None
            ),
            source_event=event_name,
        )

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        return not self.passed

    @property
    def findings_count(self) -> int:
        return max(len(self.findings), self.logged_findings_count or 0)

    @property
    def normalized_findings(self) -> tuple[CritiqueFindingArtifact, ...]:
        return self.findings

    @property
    def event_name(self) -> str:
        if self.source_event is not None:
            return self.source_event
        if self.level == "epic":
            return "epic_critique_pass" if self.passed else "epic_critique_fail"
        return "critique_pass" if self.passed else "critique_fail"

    @property
    def concise_summary(self) -> str:
        if self.summary:
            return self.summary
        if self.error:
            return self.error
        if self.findings:
            issues = [finding.issue for finding in self.findings if finding.issue][:2]
            if issues:
                remaining = self.findings_count - len(issues)
                suffix = f"; +{remaining} more" if remaining > 0 else ""
                return "; ".join(issues) + suffix
        if self.findings_count:
            return f"{self.findings_count} findings"
        return "No findings"

    @property
    def event_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "critique_type": self.critique_type,
            "critique_model": self.critique_model,
            "findings_count": self.findings_count,
        }
        if self.story_id is not None:
            payload["story_id"] = self.story_id
        if self.attempt is not None:
            payload["attempt"] = self.attempt
        if self.turns is not None:
            payload["turns"] = self.turns
        if self.summary:
            payload["summary"] = self.summary
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.raw_response:
            payload["raw_response"] = self.raw_response
        if self.error:
            payload["error"] = self.error
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "level": self.level,
            "status": self.status,
            "critique_type": self.critique_type,
            "critique_model": self.critique_model,
            "findings": [finding.to_dict() for finding in self.findings],
            "findings_count": self.findings_count,
            "summary": self.summary,
        }
        optional_fields = {
            "story_id": self.story_id,
            "attempt": self.attempt,
            "turns": self.turns,
            "raw_response": self.raw_response,
            "error": self.error,
            "source_event": self.source_event,
        }
        payload.update({key: value for key, value in optional_fields.items() if value not in (None, "")})
        return payload

    def context_payload(self, *, limit: int | None = None) -> dict[str, Any]:
        findings = [finding.to_dict() for finding in self.findings]
        if limit is not None:
            findings = findings[:limit]

        payload: dict[str, Any] = {
            "critique_summary": self.concise_summary,
            "findings_count": self.findings_count,
        }
        if findings:
            payload["critique_findings"] = findings
        if self.error:
            payload["critique_error"] = self.error
        return payload


@dataclass(frozen=True)
class FailureClassificationArtifact:
    """Typed story failure classification used for retries and exit decisions."""

    category: str
    evidence: str
    pattern: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailureClassificationArtifact":
        return cls(
            category=str(payload["category"]),
            evidence=str(payload["evidence"]),
            pattern=str(payload["pattern"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "evidence": self.evidence,
            "pattern": self.pattern,
        }

    @property
    def terminal_reason(self) -> str:
        return f"Failure ({self.category}): {self.pattern} -- {self.evidence[:200]}"


@dataclass(frozen=True)
class PreflightArtifact:
    """Typed result for story pre-flight checks."""

    passed: bool
    issues: tuple[str, ...] = ()
    is_minor: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PreflightArtifact":
        issues = payload.get("issues", [])
        if not isinstance(issues, list):
            raise TypeError("issues must be a list")
        return cls(
            passed=bool(payload["passed"]),
            issues=tuple(str(issue) for issue in issues),
            is_minor=bool(payload.get("is_minor", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": list(self.issues),
            "is_minor": self.is_minor,
        }

    @property
    def description(self) -> str:
        return "; ".join(self.issues)

    @property
    def combined_issues(self) -> str:
        return "\n".join(self.issues)


@dataclass(frozen=True)
class StoryFailureContextArtifact:
    """Typed failure context used in retry prompts and exit_to_human payloads."""

    story_id: str
    attempt: int
    last_error: str
    files_affected: tuple[str, ...]
    jsonl_excerpt: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StoryFailureContextArtifact":
        files_affected = payload.get("files_affected", [])
        if not isinstance(files_affected, list):
            raise TypeError("files_affected must be a list")
        return cls(
            story_id=str(payload["story_id"]),
            attempt=int(payload["attempt"]),
            last_error=str(payload["last_error"]),
            files_affected=tuple(str(path) for path in files_affected),
            jsonl_excerpt=str(payload["jsonl_excerpt"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_id": self.story_id,
            "attempt": self.attempt,
            "last_error": self.last_error,
            "files_affected": list(self.files_affected),
            "jsonl_excerpt": self.jsonl_excerpt,
        }

    @property
    def prompt_block(self) -> str:
        return (
            f"\n\n---\n## Failure Feedback (Attempt {self.attempt})\n\n"
            f"**Error:** {self.last_error}\n"
            f"**Files modified:** {', '.join(self.files_affected)}\n"
            f"**JSONL excerpt:** {self.jsonl_excerpt}\n"
        )

    @property
    def event_context(self) -> dict[str, Any]:
        return self.to_dict()


@dataclass(frozen=True)
class CheckpointCriterionResultArtifact:
    """Typed result for one validation checkpoint criterion."""

    criterion: str
    status: str
    evidence: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CheckpointCriterionResultArtifact":
        evidence = payload.get("evidence", {})
        if not isinstance(evidence, dict):
            raise TypeError("evidence must be a dict")
        return cls(
            criterion=str(payload["criterion"]),
            status=str(payload["status"]),
            evidence=evidence,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class CheckpointRunArtifact:
    """Typed validation checkpoint result and JSONL event boundary."""

    story_id: str
    check_type: str
    passed: bool
    results: tuple[CheckpointCriterionResultArtifact, ...]
    failure_reason: str | None = None
    failure_category: str | None = None
    raw_output: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CheckpointRunArtifact":
        results_payload = payload.get("results", [])
        if not isinstance(results_payload, list):
            raise TypeError("results must be a list")
        return cls(
            story_id=str(payload["story_id"]),
            check_type=str(payload["check_type"]),
            passed=bool(payload["passed"]),
            results=tuple(CheckpointCriterionResultArtifact.from_dict(item) for item in results_payload),
            failure_reason=(
                str(payload["failure_reason"]) if payload.get("failure_reason") is not None else None
            ),
            failure_category=(
                str(payload["failure_category"])
                if payload.get("failure_category") is not None
                else None
            ),
            raw_output=str(payload.get("raw_output", "")),
        )

    @classmethod
    def from_event(
        cls,
        event: dict[str, Any] | "RunEventArtifact",
    ) -> "CheckpointRunArtifact":
        event_artifact = event if isinstance(event, RunEventArtifact) else RunEventArtifact.from_dict(event)
        if event_artifact.event not in {"validation_pass", "validation_fail"}:
            raise ValueError(f"Cannot build CheckpointRunArtifact from event {event_artifact.event}")

        return cls(
            story_id=str(event_artifact.get("story_id")),
            check_type=str(event_artifact.get("check_type")),
            passed=event_artifact.event == "validation_pass",
            results=tuple(
                CheckpointCriterionResultArtifact.from_dict(item)
                for item in event_artifact.get("results", [])
                if isinstance(item, dict)
            ),
            failure_reason=(
                str(event_artifact.get("failure_reason"))
                if event_artifact.get("failure_reason") is not None
                else None
            ),
            failure_category=(
                str(event_artifact.get("failure_category"))
                if event_artifact.get("failure_category") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "story_id": self.story_id,
            "check_type": self.check_type,
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
            "raw_output": self.raw_output,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        return payload

    @property
    def event_name(self) -> str:
        return "validation_pass" if self.passed else "validation_fail"

    @property
    def event_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "story_id": self.story_id,
            "check_type": self.check_type,
            "results": [result.to_dict() for result in self.results],
        }
        if not self.passed and self.failure_category:
            payload["failure_category"] = self.failure_category
        if not self.passed and self.failure_reason:
            payload["failure_reason"] = self.failure_reason
        return payload


@dataclass(frozen=True)
class RunEventArtifact:
    """Typed JSONL event entry for epic and story logs."""

    run_id: str
    ts: str
    event: str
    data: dict[str, Any]
    schema_v: int = RUN_EVENT_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunEventArtifact":
        data = {
            key: value
            for key, value in payload.items()
            if key not in {"schema_v", "run_id", "ts", "event"}
        }
        schema_v = int(payload.get("schema_v", RUN_EVENT_SCHEMA_VERSION))
        return cls(
            schema_v=schema_v,
            run_id=str(payload["run_id"]),
            ts=str(payload["ts"]),
            event=str(payload["event"]),
            data=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_v": self.schema_v,
            "run_id": self.run_id,
            "ts": self.ts,
            "event": self.event,
            **self.data,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if key == "schema_v":
            return self.schema_v
        if key == "run_id":
            return self.run_id
        if key == "ts":
            return self.ts
        if key == "event":
            return self.event
        return self.data.get(key, default)


@dataclass(frozen=True)
class StoryRunArtifact:
    """Derived per-story execution snapshot reconstructed from JSONL events."""

    story_id: str
    status: str
    attempt: int
    has_passing_test: bool
    latest_test_file_path: str | None
    review_failures: tuple[TestReviewArtifact, ...]
    last_checkpoint: CheckpointRunArtifact | None
    last_error: str | None
    last_event: RunEventArtifact | None

    @classmethod
    def from_events(
        cls,
        events: list[dict[str, Any]] | list[RunEventArtifact],
        story_id: str,
    ) -> "StoryRunArtifact":
        event_artifacts = [
            event if isinstance(event, RunEventArtifact) else RunEventArtifact.from_dict(event)
            for event in events
        ]
        story_events = [event for event in event_artifacts if event.get("story_id") == story_id]
        if story_events:
            story_events.sort(key=lambda event: event.ts)

        last_event = story_events[-1] if story_events else None
        attempt = max(
            (
                int(event.get("attempt"))
                for event in story_events
                if event.get("attempt") is not None
            ),
            default=0,
        )

        latest_test_file_path = next(
            (
                str(event.get("test_file_path"))
                for event in reversed(story_events)
                if event.get("test_file_path") is not None
            ),
            None,
        )
        has_passing_test = any(event.event == "test_review_pass" for event in story_events)
        review_failures = tuple(
            TestReviewArtifact.from_dict(feedback)
            for event in story_events
            if event.event == "test_review_fail"
            for feedback in [event.get("reviewer_feedback")]
            if isinstance(feedback, dict) and "verdict" in feedback
        )
        last_checkpoint = next(
            (
                CheckpointRunArtifact.from_event(event)
                for event in reversed(story_events)
                if event.event in {"validation_pass", "validation_fail"}
            ),
            None,
        )
        last_error = next(
            (
                str(event.get("error"))
                for event in reversed(story_events)
                if event.get("error") is not None
            ),
            None,
        )

        if last_event is None:
            status = "pending"
        elif last_event.event == "test_review_pass":
            status = "tests_passed"
        elif last_event.event in ("test_gen_started", "test_gen_attempt", "test_review_fail"):
            status = "tests_running"
        elif last_event.event == "story_complete":
            status = "complete"
        elif last_event.event == "exit_to_human":
            status = "exit_to_human"
        elif last_event.event in (
            "story_failed",
            "agent_failed",
            "validation_fail",
            "critique_fail",
            "critique_failed",
        ):
            status = "failed"
        elif last_event.event in ("story_started", "preflight_pass", "agent_dispatched"):
            status = "running"
        else:
            status = last_event.event

        return cls(
            story_id=story_id,
            status=status,
            attempt=attempt,
            has_passing_test=has_passing_test,
            latest_test_file_path=latest_test_file_path,
            review_failures=review_failures,
            last_checkpoint=last_checkpoint,
            last_error=last_error,
            last_event=last_event,
        )

    @property
    def failure_reason(self) -> str | None:
        if self.last_event is not None:
            if self.last_event.event == "validation_fail" and self.last_checkpoint is not None:
                if self.last_checkpoint.failure_reason:
                    return self.last_checkpoint.failure_reason

            for key in ("reason", "failure_reason", "error"):
                value = self.last_event.get(key)
                if value:
                    return str(value)

        if self.last_checkpoint is not None and self.last_checkpoint.failure_reason:
            return self.last_checkpoint.failure_reason
        return self.last_error

    @property
    def failure_category(self) -> str | None:
        if self.last_event is not None:
            category = self.last_event.get("failure_category")
            if category:
                return str(category)
        if self.last_checkpoint is not None and self.last_checkpoint.failure_category:
            return self.last_checkpoint.failure_category
        return None

    @property
    def failure_context(self) -> StoryFailureContextArtifact | None:
        if self.last_event is None:
            return None

        context = self.last_event.get("context")
        if not isinstance(context, dict):
            return None

        try:
            return StoryFailureContextArtifact.from_dict(context)
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def checkpoint_summary_lines(self) -> tuple[str, ...]:
        if self.last_checkpoint is None:
            return ()

        return tuple(
            f"- [{'PASS' if result.status == 'pass' else 'FAIL'}] {result.criterion}"
            for result in self.last_checkpoint.results
        )


@dataclass(frozen=True)
class RunArtifact:
    """Derived orchestration snapshot for one epic run."""

    run_id: str
    epic_number: int | None
    stage: str
    next_action: str
    completed_stories: tuple[str, ...]
    failed_story_id: str | None
    stories_with_passing_tests: tuple[str, ...]
    last_event: RunEventArtifact | None
    decision_gate: str | None = None
    dispatch_ids: tuple[str, ...] = ()

    @classmethod
    def from_logs(
        cls,
        events: list[dict[str, Any]] | list[RunEventArtifact],
        run_id: str,
        *,
        epic_number: int | None = None,
        has_plan: bool = False,
        dispatches: list[dict[str, Any]] | list[DispatchArtifact] | None = None,
    ) -> "RunArtifact":
        event_artifacts = [
            event if isinstance(event, RunEventArtifact) else RunEventArtifact.from_dict(event)
            for event in events
        ]
        run_events = [event for event in event_artifacts if event.run_id == run_id]
        if run_events:
            run_events.sort(key=lambda event: event.ts)

        completed_stories = tuple(
            sorted(
                {
                    str(event.get("story_id"))
                    for event in run_events
                    if event.event == "story_complete" and event.get("story_id") is not None
                }
            )
        )
        stories_with_passing_tests = tuple(
            sorted(
                {
                    str(event.get("story_id"))
                    for event in event_artifacts
                    if event.event == "test_review_pass" and event.get("story_id") is not None
                }
            )
        )
        last_event = run_events[-1] if run_events else None

        if last_event is None:
            next_action = "start"
            failed_story_id = None
        elif last_event.event == "epic_complete":
            next_action = "epic_complete"
            failed_story_id = None
        elif last_event.event in ("exit_to_human", "epic_critique_fail"):
            next_action = "exit_to_human"
            failed_story_id = last_event.get("story_id")
        elif last_event.event in (
            "story_failed",
            "agent_failed",
            "validation_fail",
            "critique_fail",
            "critique_failed",
        ):
            next_action = "retry_story"
            failed_story_id = last_event.get("story_id")
        elif last_event.event in ("test_gen_started", "test_gen_attempt", "test_review_fail", "tests_approved"):
            next_action = "test_generation"
            failed_story_id = None
        else:
            next_action = "continue"
            failed_story_id = None

        has_plan_committed = any(event.event == "plan_committed" for event in event_artifacts)
        has_epic_complete = any(
            event.event == "epic_complete" and event.run_id == run_id for event in event_artifacts
        )
        has_epic_failed = any(
            event.event == "epic_failed" and event.run_id == run_id for event in event_artifacts
        )

        if has_epic_complete:
            stage = "complete"
        elif has_epic_failed:
            stage = "failed"
        elif has_plan_committed:
            stage = "execution"
        elif has_plan:
            stage = "planned"
        else:
            stage = "planning"

        gate_event = next(
            (
                event
                for event in reversed(run_events)
                if event.event in ("plan_approved", "plan_revised", "plan_rejected")
            ),
            None,
        )
        decision_gate = gate_event.event.removeprefix("plan_") if gate_event is not None else None

        dispatch_ids: tuple[str, ...] = ()
        if dispatches:
            dispatch_artifacts = [
                dispatch if isinstance(dispatch, DispatchArtifact) else DispatchArtifact.from_dict(dispatch)
                for dispatch in dispatches
            ]
            dispatch_ids = tuple(
                dispatch.dispatch_id
                for dispatch in dispatch_artifacts
                if dispatch.run_id == run_id
            )

        return cls(
            run_id=run_id,
            epic_number=epic_number,
            stage=stage,
            next_action=next_action,
            completed_stories=completed_stories,
            failed_story_id=failed_story_id if failed_story_id is None else str(failed_story_id),
            stories_with_passing_tests=stories_with_passing_tests,
            last_event=last_event,
            decision_gate=decision_gate,
            dispatch_ids=dispatch_ids,
        )

    def to_resume_state(self) -> dict[str, Any]:
        return {
            "completed_stories": list(self.completed_stories),
            "last_event": self.last_event.to_dict() if self.last_event is not None else None,
            "next_action": self.next_action,
            "failed_story_id": self.failed_story_id,
            "stories_with_passing_tests": list(self.stories_with_passing_tests),
        }
