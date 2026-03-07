"""Deterministic prompt compilation helpers for epic workflow prompts.

This module separates prompt construction from prompt execution so prompts can
be tested as pure artefacts without dispatching live models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from workflow.dispatch import estimate_tokens


@dataclass(frozen=True)
class PromptSection:
    """One logical section in a compiled prompt."""

    heading: str
    body: str

    def render(self) -> str:
        return f"{self.heading}\n\n{self.body}".strip()


@dataclass(frozen=True)
class PromptArtifact:
    """Compiled prompt with inspectable sections and token estimate."""

    role: str
    sections: tuple[PromptSection, ...]

    @property
    def text(self) -> str:
        return "\n\n---\n\n".join(section.render() for section in self.sections)

    @property
    def approx_tokens(self) -> int:
        return estimate_tokens(self.text)


def make_prompt_artifact(role: str, sections: list[PromptSection]) -> PromptArtifact:
    """Build a prompt artefact from ordered sections."""
    return PromptArtifact(role=role, sections=tuple(sections))


def compact_plan_for_review(plan_json: dict[str, Any]) -> dict[str, Any]:
    """Trim plan.json to only the fields needed for verification/revision.

    Verifier and revision prompts do not need verbose agent guidance such as
    architectural_context or navigation_hints repeated verbatim.
    """

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


def render_json_block(tag: str, payload: Any) -> str:
    """Render a tagged JSON payload block."""
    return f"<{tag}>\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n</{tag}>"
