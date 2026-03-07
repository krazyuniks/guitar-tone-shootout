"""Compile-only prompt suite for epic workflow debugging and tests."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from workflow.plan_generator import (
    _build_planner_prompt,
    build_targeted_phase_a_revision_prompt,
    build_targeted_phase_b_revision_prompt,
)
from workflow.plan_verifier import _build_verifier_prompt


@dataclass(frozen=True)
class CompiledPromptInfo:
    """One compile-only prompt artefact."""

    role: str
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def approx_tokens(self) -> int:
        return len(self.text) // 4


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def _read_plan(path: Path) -> dict:
    return json.loads(_read_text(path))


def compile_planner_prompt(epic_dir: Path) -> CompiledPromptInfo:
    """Compile the planner prompt for an epic directory."""
    epic_md = _read_text(epic_dir / "EPIC.md")
    epic_number = int(epic_dir.name.removeprefix("E"))
    return CompiledPromptInfo("planner", _build_planner_prompt(epic_md, epic_number))


def compile_verifier_prompt(epic_dir: Path) -> CompiledPromptInfo:
    """Compile the verifier prompt for an epic directory with plan.json."""
    epic_md = _read_text(epic_dir / "EPIC.md")
    plan = _read_plan(epic_dir / "plan.json")
    return CompiledPromptInfo("plan_verifier", _build_verifier_prompt(plan, epic_md))


def compile_phase_a_revision_prompt(epic_dir: Path, errors: list[str]) -> CompiledPromptInfo:
    """Compile the Phase A revision prompt from plan.json and validation errors."""
    plan_json_str = _read_text(epic_dir / "plan.json")
    return CompiledPromptInfo(
        "planner_revision_phase_a",
        build_targeted_phase_a_revision_prompt(plan_json_str, errors),
    )


def compile_phase_b_revision_prompt(
    epic_dir: Path,
    verifier_result: dict,
) -> CompiledPromptInfo:
    """Compile the Phase B revision prompt from epic, plan, and verifier result."""
    epic_md = _read_text(epic_dir / "EPIC.md")
    plan_json_str = _read_text(epic_dir / "plan.json")
    return CompiledPromptInfo(
        "planner_revision_phase_b",
        build_targeted_phase_b_revision_prompt(epic_md, plan_json_str, verifier_result),
    )


def compile_prompt_suite(
    epic_dir: Path,
    *,
    phase_a_errors: list[str] | None = None,
    verifier_result: dict | None = None,
) -> dict[str, CompiledPromptInfo]:
    """Compile the available prompt stages for an epic without dispatching."""
    suite: dict[str, CompiledPromptInfo] = {
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
    verifier_result: dict | None = None,
) -> dict[str, CompiledPromptInfo]:
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
