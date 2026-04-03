"""Shared GitHub comment helpers for epic workflow advisory output."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from workflow.artifacts import CritiqueRunArtifact

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GH_REPO = "krazyuniks/guitar-tone-shootout"


def comment_on_epic(epic_number: int, body: str) -> str | None:
    """Post a comment on a GitHub epic issue."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(epic_number),
                "--repo",
                GH_REPO,
                "--body",
                body,
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            logger.info("GitHub comment posted: %s", url)
            return url
        logger.warning("Failed to post GitHub comment: %s", result.stderr.strip())
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Failed to post GitHub comment: %s", exc)
        return None


def build_critique_findings_comment(
    *,
    gate_type: str,
    critique_run: CritiqueRunArtifact,
    story_id: str | None = None,
) -> str:
    """Build a unified advisory comment for critique findings."""
    finding_lines = [finding.markdown_text for finding in critique_run.normalized_findings]
    if not finding_lines:
        finding_lines.append(f"- {critique_run.concise_summary}")

    story_line = f"**Story:** `{story_id}`\n\n" if story_id else ""
    return (
        f"## Critique Findings ({gate_type})\n\n"
        f"{story_line}"
        + "\n".join(finding_lines)
        + "\n\n*Advisory - pipeline continued.*"
    )
