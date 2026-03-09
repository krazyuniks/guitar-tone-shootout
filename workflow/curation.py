"""Bounded curation stage between repo-facts and plan generation."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from workflow.artifacts import CurationArtifact, EpicArtifact, RepoFactsArtifact
from workflow.dispatch import dispatch_agent, get_dispatch_params
from workflow.epic_config import EpicConfig
from workflow.models import Curation
from workflow.prompt_compiler import PromptSection, make_prompt_artifact

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


class CurationError(Exception):
    """Raised when curation generation fails."""


def _read_optional_codebase_hints(project_root: Path) -> list[str]:
    """Return a compact deterministic list of optional codebase hint files."""
    codebase_dir = project_root / ".planning" / "codebase"
    if not codebase_dir.is_dir():
        return []

    return [
        path.name
        for path in sorted(codebase_dir.iterdir())
        if path.is_file() and path.suffix == ".md"
    ][:8]


def make_curation_prompt(
    epic: EpicArtifact,
    repo_facts: RepoFactsArtifact,
    *,
    optional_codebase_hints: list[str] | None = None,
):
    """Compile the bounded curation prompt from typed epic workflow artifacts."""
    hint_lines = optional_codebase_hints or []
    hint_text = (
        "\n".join(f"- {name}" for name in hint_lines)
        if hint_lines
        else "No prebuilt codebase hint files are present for this epic."
    )

    return make_prompt_artifact(
        role="curation",
        sections=[
            PromptSection(
                "# Task: Curate Planning Inputs",
                (
                    f"Produce a bounded `curation.json` for epic #{epic.epic_number}. "
                    "This stage shapes planning; it does not produce final stories, "
                    "final checkpoints, or a final execution schema.\n\n"
                    "Read AGENTS.md and DEVELOPMENT.md first for project conventions.\n\n"
                    "Output only a single JSON object matching the provided schema. "
                    "Do not emit markdown or analysis text. Use the StructuredOutput tool "
                    "for the final answer, and pass the curation object itself as the tool "
                    "input. Do NOT wrap it in `result`, `curation`, `output`, or any outer key."
                ),
            ),
            PromptSection("## Epic Contract", epic.prompt_block),
            PromptSection("## Repo Facts", repo_facts.prompt_block),
            PromptSection(
                "## Optional Codebase Hints",
                (
                    "These files may exist if maintainers already generated repo maps. "
                    "They are optional acceleration only, never more authoritative than "
                    "live repo inspection.\n\n"
                    f"{hint_text}"
                ),
            ),
            PromptSection(
                "## Curation Boundaries",
                """You are curating inputs for the planner, not replacing the planner.

Stay strictly bounded to:
- `candidate_journeys`
- `story_slices`
- `missing_assumptions`
- `scope_tensions`
- `planner_handoff`

Rules:
1. Do NOT emit final story IDs, final checkpoints, or full plan.json structure.
2. Use repo evidence to avoid invented routes, pages, or components.
3. Keep every item concise and specific.
4. Prefer a small number of high-signal items over exhaustive brainstorming.
5. If something is ambiguous, capture it under `missing_assumptions` or `scope_tensions` instead of guessing.
6. If repo conventions differ from the epic contract, surface that mismatch
   explicitly and factually: name the epic contract, the repo convention, and
   why the mismatch matters to planning fidelity.
7. Do NOT recommend which contract should win. Do NOT tell the planner to
   replace the epic contract with a repo-preferred route, field, or transport.""",
            ),
            PromptSection(
                "## Output",
                """Return one complete JSON object matching the curation schema.
The object must be directly useful as planner input for this epic.""",
            ),
        ],
    )


def _parse_structured_curation(result_output: str) -> Curation:
    """Parse a dispatch result into a validated Curation model."""
    text = result_output.strip()

    fence_match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    json_text = fence_match.group(1).strip() if fence_match else text

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        pos = exc.pos or 0
        context_start = max(0, pos - 200)
        context_end = min(len(json_text), pos + 200)
        error_context = json_text[context_start:context_end]
        marker_pos = pos - context_start
        marker_line = " " * marker_pos + "^ ERROR HERE"
        raise CurationError(
            f"Curation output is not valid JSON: {exc}\n"
            f"Context around error (char {pos}):\n"
            f"{error_context}\n{marker_line}"
        ) from exc
    try:
        return Curation.model_validate(data)
    except Exception as exc:
        raise CurationError(f"Curation JSON failed Pydantic validation: {exc}") from exc


def generate_curation(
    epic_dir: Path,
    config: EpicConfig | None = None,
) -> tuple[Path, Path]:
    """Generate CURATION.md and curation.json for an epic directory."""
    try:
        epic = EpicArtifact.from_epic_dir(epic_dir)
        repo_facts = RepoFactsArtifact.from_epic_dir(epic_dir)
    except FileNotFoundError as exc:
        raise CurationError(str(exc)) from exc
    except ValueError as exc:
        raise CurationError(str(exc)) from exc

    prompt_artifact = make_curation_prompt(
        epic,
        repo_facts,
        optional_codebase_hints=_read_optional_codebase_hints(PROJECT_ROOT),
    )
    prompt = prompt_artifact.text
    curator_model = config.models.planner if config else "sonnet"

    logger.info(
        "Dispatching %s curation for epic #%d (%d chars, ~%d tokens)",
        curator_model,
        epic.epic_number,
        len(prompt),
        len(prompt) // 4,
    )

    mcp_servers, timeout = get_dispatch_params("planning", config)
    result = dispatch_agent(
        prompt=prompt,
        model=curator_model,
        json_schema=Curation.model_json_schema(),
        cwd=PROJECT_ROOT,
        mcp_servers=mcp_servers,
        timeout=timeout,
        role="curation",
    )

    if not result.success:
        raise CurationError(
            f"Curation dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    curation = _parse_structured_curation(result.output)
    curation_md_path, curation_json_path = CurationArtifact.from_model(curation).write(epic_dir)
    logger.info("Wrote curation.json to %s", curation_json_path)
    logger.info("Wrote CURATION.md to %s", curation_md_path)

    return curation_md_path, curation_json_path


def main() -> None:
    """CLI entry point: python -m workflow.curation <epic_number>."""
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
        print(f"Error: Epic directory not found: {epic_dir}. Run ingestion first.", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        curation_md_path, curation_json_path = generate_curation(epic_dir)
        print(f"Curation generated for epic #{epic_number}:")
        print(f"  CURATION.md:   {curation_md_path.relative_to(PROJECT_ROOT)}")
        print(f"  curation.json: {curation_json_path.relative_to(PROJECT_ROOT)}")
    except CurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
