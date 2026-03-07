"""Compile-only prompt suite for epic workflow debugging and tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow.artifacts import (
    EpicArtifact,
    PlanArtifact,
    RevisionRequestArtifact,
    VerifierFeedbackArtifact,
)
from workflow.plan_generator import (
    make_phase_a_revision_prompt,
    make_phase_b_revision_prompt,
    make_planner_prompt,
)
from workflow.plan_verifier import make_verifier_prompt
from workflow.prompt_compiler import PromptArtifact


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def _read_plan(path: Path) -> PlanArtifact:
    return PlanArtifact.from_json_text(_read_text(path))


def compile_planner_prompt(epic_dir: Path) -> PromptArtifact:
    """Compile the planner prompt for an epic directory."""
    return make_planner_prompt(EpicArtifact.from_epic_dir(epic_dir))


def compile_verifier_prompt(epic_dir: Path) -> PromptArtifact:
    """Compile the verifier prompt for an epic directory with plan.json."""
    return make_verifier_prompt(
        _read_plan(epic_dir / "plan.json"),
        EpicArtifact.from_epic_dir(epic_dir),
    )


def compile_phase_a_revision_prompt(epic_dir: Path, errors: list[str]) -> PromptArtifact:
    """Compile the Phase A revision prompt from plan.json and validation errors."""
    return make_phase_a_revision_prompt(
        RevisionRequestArtifact.for_phase_a(
            _read_plan(epic_dir / "plan.json"),
            errors,
        )
    )


def compile_phase_b_revision_prompt(
    epic_dir: Path,
    verifier_result: dict | VerifierFeedbackArtifact,
) -> PromptArtifact:
    """Compile the Phase B revision prompt from epic, plan, and verifier result."""
    feedback = (
        verifier_result
        if isinstance(verifier_result, VerifierFeedbackArtifact)
        else VerifierFeedbackArtifact.from_dict(verifier_result)
    )
    return make_phase_b_revision_prompt(
        RevisionRequestArtifact.for_phase_b(
            EpicArtifact.from_epic_dir(epic_dir),
            _read_plan(epic_dir / "plan.json"),
            feedback,
        )
    )


def compile_prompt_suite(
    epic_dir: Path,
    *,
    phase_a_errors: list[str] | None = None,
    verifier_result: dict | VerifierFeedbackArtifact | None = None,
) -> dict[str, PromptArtifact]:
    """Compile the available prompt stages for an epic without dispatching."""
    suite: dict[str, PromptArtifact] = {
        "planner": compile_planner_prompt(epic_dir),
    }

    if (epic_dir / "plan.json").exists():
        suite["plan_verifier"] = compile_verifier_prompt(epic_dir)

    if phase_a_errors:
        suite["planner_revision_phase_a"] = compile_phase_a_revision_prompt(epic_dir, phase_a_errors)

    if verifier_result:
        suite["planner_revision_phase_b"] = compile_phase_b_revision_prompt(
            epic_dir,
            verifier_result,
        )

    return suite


def write_prompt_suite(
    epic_dir: Path,
    *,
    phase_a_errors: list[str] | None = None,
    verifier_result: dict | VerifierFeedbackArtifact | None = None,
) -> dict[str, PromptArtifact]:
    """Compile prompts and write them to compiled-prompts/ under the epic dir."""
    suite = compile_prompt_suite(
        epic_dir,
        phase_a_errors=phase_a_errors,
        verifier_result=verifier_result,
    )
    out_dir = epic_dir / "compiled-prompts"
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, prompt in suite.items():
        (out_dir / f"{name}.txt").write_text(prompt.text, encoding="utf-8")

    return suite


def main() -> None:
    """CLI entry point for compile-only prompt generation."""
    parser = argparse.ArgumentParser(description="Compile epic workflow prompts without dispatching")
    parser.add_argument("epic_number", type=int, help="Epic number, e.g. 146")
    parser.add_argument(
        "--verifier-response",
        type=Path,
        help="Optional path to a verifier JSON response file for Phase B revision prompt compilation",
    )
    parser.add_argument(
        "--phase-a-error",
        action="append",
        default=[],
        help="Optional Phase A validation error to include for revision prompt compilation",
    )
    args = parser.parse_args()

    epic_dir = Path(__file__).resolve().parent.parent / ".planning" / "epics" / f"E{args.epic_number}"
    verifier_result = None
    if args.verifier_response:
        verifier_result = json.loads(args.verifier_response.read_text(encoding="utf-8"))

    suite = write_prompt_suite(
        epic_dir,
        phase_a_errors=args.phase_a_error or None,
        verifier_result=verifier_result,
    )

    for name, prompt in suite.items():
        print(f"{name}: {prompt.chars} chars, ~{prompt.approx_tokens} tokens")


if __name__ == "__main__":
    main()
