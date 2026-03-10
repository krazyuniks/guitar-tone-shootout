#!/usr/bin/env python3
"""Selective context assembly for the V2 epic planner.

Reads EPIC.md, performs LLM-based area detection (via Haiku), and injects
only the wiki sections and codebase files relevant to the detected areas.

Usage:
    python workflow/context_assembler.py --epic-dir .planning/epics/E95/ --project-root .
    python workflow/context_assembler.py --epic-dir .planning/epics/E95/
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AssemblyError(Exception):
    """Raised when context assembly fails."""


# ---------------------------------------------------------------------------
# Area descriptions (used in LLM prompt for area detection)
# ---------------------------------------------------------------------------

AREA_DESCRIPTIONS: dict[str, str] = {
    "signal_chain": "Signal chain block types, ordering, validation rules (HEAD vs FULL_RIG, IR requirements)",
    "gear_model": "Unified gear model, sources, sync records, gear library, UserGear",
    "database_architecture": "Single database with BC table prefixes (core_*, t3k_*, msg_*), pgmq, migrations",
    "frontend_layers": "Astro SSG, Jinja2 SSR, HTMX fragments, page templates, React islands",
    "job_processing": "TaskIQ jobs, pgmq consumers, background workers, queues, retry strategy",
    "audio_processing": "NAM, IR, loudness normalization, audio pipeline, pedalboard",
    "data_model": "Tables, columns, relations, SQLAlchemy ORM, entity lifecycle",
    "orm_patterns": "Repository pattern, transactions, eager/lazy loading",
    "api_contract": "Endpoints, Pydantic schemas, REST vs HTML, validation, pagination",
    "security": "Auth, OAuth, session cookies, ownership checks, CORS, rate limiting",
    "testing": "Unit/integration/E2E boundaries, no-mock policy, real services",
}


# ---------------------------------------------------------------------------
# Area-to-wiki-section mapping
# ---------------------------------------------------------------------------
# Maps detected areas to the CONTEXT marker names in GTS-Technical-Architecture.md.
# The `architecture-layers` section is always included for structural orientation.

AREA_TO_WIKI_SECTIONS: dict[str, list[str]] = {
    "data_model": ["domain-model", "persistence", "design-patterns"],
    "orm_patterns": ["domain-model", "persistence", "design-patterns"],
    "api_contract": ["api-design", "auth"],
    "frontend_layers": ["frontend"],
    "signal_chain": ["domain-model", "api-design"],
    "gear_model": ["domain-model", "api-design"],
    "audio_processing": ["audio", "domain-model"],
    "job_processing": ["data-ingestion", "infrastructure"],
    "database_architecture": ["persistence", "data-ingestion"],
    "security": ["auth", "api-design"],
    "testing": ["testing"],
}

# Always-included wiki section (provides structural orientation)
ALWAYS_INCLUDE_SECTIONS: list[str] = ["architecture-layers"]

# Domain-specific wiki files -- loaded in full when the corresponding area is detected
AREA_TO_WIKI_FILES: dict[str, str] = {
    "frontend_layers": "Frontend-Architecture",
    "audio_processing": "Audio-Processing",
    # video area isn't in AREA_DESCRIPTIONS, but audio_processing + job_processing
    # covers video rendering via the Remotion architecture
}

# GTS-Video-Architecture is loaded when both audio_processing and job_processing
# are detected (video rendering involves both)
REMOTION_AREAS: set[str] = {"audio_processing", "job_processing"}


# ---------------------------------------------------------------------------
# Area-to-codebase-file mapping
# ---------------------------------------------------------------------------
# STRUCTURE.md is always included. Others are conditional.

ALWAYS_INCLUDE_CODEBASE: list[str] = ["STRUCTURE"]

AREA_TO_CODEBASE_FILES: dict[str, list[str]] = {
    "data_model": ["SCHEMA"],
    "orm_patterns": ["SCHEMA"],
    "api_contract": ["ENDPOINTS"],
    "signal_chain": ["SCHEMA", "ENDPOINTS"],
    "gear_model": ["SCHEMA", "ENDPOINTS"],
    "database_architecture": ["SCHEMA", "IMPORTS"],
    "audio_processing": ["IMPORTS"],
    "job_processing": ["IMPORTS"],
    "testing": ["TESTS"],
    "security": ["ENDPOINTS"],
    "frontend_layers": ["ENDPOINTS"],
}


# ---------------------------------------------------------------------------
# Source directories for freshness checks
# ---------------------------------------------------------------------------
# The codebase mapper generates files from these source trees.
# If any source file is newer than the mapper output, we warn.

FRESHNESS_SOURCE_DIRS: list[str] = [
    "libs",
    "apps",
    "sources",
    "tests",
]


# ---------------------------------------------------------------------------
# LLM-based area detection
# ---------------------------------------------------------------------------

AREA_DETECTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "areas": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": sorted(AREA_DESCRIPTIONS.keys()),
            },
        },
    },
    "required": ["areas"],
    "additionalProperties": False,
}


def _build_area_prompt(epic_body: str) -> str:
    """Build the prompt for LLM area detection."""
    area_list = "\n".join(f"- **{area_id}**: {desc}" for area_id, desc in AREA_DESCRIPTIONS.items())
    return (
        "You are a context selector for a software project planner. "
        "Given an epic description, identify which architecture areas are relevant.\n\n"
        "## Available Areas\n\n"
        f"{area_list}\n\n"
        "## Epic Description\n\n"
        f"{epic_body}\n\n"
        "## Instructions\n\n"
        "Return ONLY the areas that are directly relevant to implementing this epic. "
        "Be selective — fewer, more precise areas produce better plans than broad matches. "
        "If no specific area applies, return an empty list."
    )


def detect_areas(epic_body: str) -> set[str]:
    """Detect relevant architecture areas using a lightweight LLM call.

    Dispatches the epic body to Haiku via ``claude -p`` with a JSON schema
    constraint. Returns a set of area IDs.

    Raises:
        AssemblyError: If the LLM call fails or returns unparseable output.
    """
    prompt = _build_area_prompt(epic_body)

    args = [
        "claude",
        "-p",
        "-",
        "--model",
        "haiku",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(AREA_DETECTION_SCHEMA),
    ]

    # Strip CLAUDECODE env var to allow nested dispatch from within a Claude session
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        completed = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise AssemblyError("Area detection timed out (30s)")

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise AssemblyError(f"Area detection failed (exit {completed.returncode}): {stderr}")

    raw = (completed.stdout or "").strip()
    if not raw:
        raise AssemblyError("Area detection returned empty output")

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssemblyError(f"Area detection returned invalid JSON: {exc}") from exc

    # Claude --output-format json wraps in an envelope with structured_output
    if isinstance(envelope, dict):
        areas_data = envelope.get("structured_output") or envelope.get("result")
        if isinstance(areas_data, str):
            with contextlib.suppress(json.JSONDecodeError):
                areas_data = json.loads(areas_data)
    else:
        areas_data = envelope

    if isinstance(areas_data, dict) and "areas" in areas_data:
        area_list = areas_data["areas"]
    elif isinstance(areas_data, list):
        area_list = areas_data
    else:
        raise AssemblyError(f"Unexpected area detection response structure: {raw[:200]}")

    valid_areas = set(AREA_DESCRIPTIONS.keys())
    return {a for a in area_list if a in valid_areas}


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def extract_sections(
    content: str,
    section_names: list[str],
) -> dict[str, str]:
    """Extract named sections from a file using CONTEXT markers.

    Reads between ``<!-- CONTEXT:name -->`` and ``<!-- /CONTEXT -->`` markers.
    Returns a dict mapping section name to the content between the markers
    (markers themselves are excluded).

    Args:
        content: Full file content to extract from.
        section_names: List of section names to extract (e.g. ``["domain-model", "auth"]``).

    Returns:
        Dict mapping found section names to their content. Missing sections
        are silently omitted.
    """
    wanted = set(section_names)
    result: dict[str, str] = {}

    # Pattern: <!-- CONTEXT:name --> ... <!-- /CONTEXT -->
    pattern = re.compile(
        r"<!-- CONTEXT:(\S+) -->\n(.*?)<!-- /CONTEXT -->",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        name = match.group(1)
        if name in wanted:
            result[name] = match.group(2).strip()

    return result


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------


def _read_file_safe(path: Path) -> str | None:
    """Read a file, returning None if it doesn't exist."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _read_epic_md(epic_dir: Path) -> str:
    """Read and return the EPIC.md content."""
    epic_md = epic_dir / "EPIC.md"
    content = _read_file_safe(epic_md)
    if content is None:
        raise AssemblyError(
            f"EPIC.md not found at {epic_md}. Run epic ingestion first: "
            f"python -m workflow.epic_ingest <number>"
        )
    return content


def _extract_epic_body(epic_md_content: str) -> str:
    """Extract the body (after YAML frontmatter) from EPIC.md."""
    match = re.match(r"^---\n.*?\n---\n(.*)", epic_md_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return epic_md_content.strip()


def _resolve_wiki_sections(
    detected_areas: set[str],
    wiki_dir: Path,
) -> dict[str, str]:
    """Load only the wiki sections relevant to detected areas.

    For GTS-Technical-Architecture.md, extracts specific sections using
    CONTEXT markers. For domain-specific wiki files (Frontend-Architecture.md,
    Audio-Processing.md, GTS-Video-Architecture.md), loads the full file
    when the corresponding area is detected.

    Returns a dict mapping descriptive labels to content strings.
    """
    result: dict[str, str] = {}

    # 1. Determine which sections to extract from GTS-Technical-Architecture.md
    needed_sections: set[str] = set(ALWAYS_INCLUDE_SECTIONS)
    for area in detected_areas:
        wiki_sections = AREA_TO_WIKI_SECTIONS.get(area, [])
        needed_sections.update(wiki_sections)

    # 2. Extract sections from the main architecture doc (hard error if missing)
    arch_path = wiki_dir / "GTS-Technical-Architecture.md"
    arch_content = _read_file_safe(arch_path)
    if arch_content is None:
        raise AssemblyError(
            f"Wiki architecture file not found: {arch_path}. "
            "Architecture context is mandatory for planning."
        )
    if needed_sections:
        extracted = extract_sections(arch_content, sorted(needed_sections))
        missing_sections = needed_sections - set(extracted.keys())
        if missing_sections:
            raise AssemblyError(
                f"Missing CONTEXT markers in {arch_path.name}: {sorted(missing_sections)}. "
                "Architecture sections are mandatory for planning."
            )
        for section_name, section_content in extracted.items():
            label = f"GTS-Technical-Architecture :: {section_name}"
            result[label] = section_content

    # 3. Load domain-specific wiki files in full when area is detected (hard error if missing)
    for area in detected_areas:
        wiki_file = AREA_TO_WIKI_FILES.get(area)
        if wiki_file is None:
            continue
        label = wiki_file
        if label in result:
            continue  # Already loaded
        path = wiki_dir / f"{wiki_file}.md"
        content = _read_file_safe(path)
        if content is None:
            raise AssemblyError(
                f"Wiki file not found: {path}. "
                f"Required by detected area '{area}'. "
                "Architecture context is mandatory for planning."
            )
        result[label] = content

    # 4. Load Video architecture when both audio and job processing detected
    if REMOTION_AREAS.issubset(detected_areas):
        video_path = wiki_dir / "GTS-Video-Architecture.md"
        content = _read_file_safe(video_path)
        if content is None:
            raise AssemblyError(
                f"Wiki file not found: {video_path}. "
                "Required when both audio_processing and job_processing areas are detected."
            )
        result["GTS-Video-Architecture"] = content

    return result


def _resolve_codebase_files(
    detected_areas: set[str],
    codebase_dir: Path,
) -> dict[str, str]:
    """Load only the codebase files relevant to detected areas.

    STRUCTURE.md is always included. Other files are loaded conditionally
    based on the detected areas.

    Returns a dict mapping filename (without extension) to content.
    """
    needed: set[str] = set(ALWAYS_INCLUDE_CODEBASE)
    for area in detected_areas:
        files = AREA_TO_CODEBASE_FILES.get(area, [])
        needed.update(files)

    result: dict[str, str] = {}
    for name in sorted(needed):
        path = codebase_dir / f"{name}.md"
        content = _read_file_safe(path)
        if content is not None:
            result[name] = content

    return result


# ---------------------------------------------------------------------------
# Freshness check
# ---------------------------------------------------------------------------


def check_freshness(
    project_root: Path,
    codebase_dir: Path,
    loaded_files: set[str],
) -> list[str]:
    """Compare codebase file mtimes against source file mtimes.

    Checks whether any Python source files in the project are newer than
    the loaded codebase analysis files. Returns a list of warning messages
    for stale files.

    Args:
        project_root: Project root directory.
        codebase_dir: Path to .planning/codebase/ directory.
        loaded_files: Set of codebase file names (without extension) that
            were loaded (e.g. {"STRUCTURE", "SCHEMA"}).

    Returns:
        List of warning strings. Empty if everything is fresh.
    """
    stale_warnings: list[str] = []

    # Find the newest source file mtime across all source directories
    newest_source_mtime: float = 0
    for src_dir_name in FRESHNESS_SOURCE_DIRS:
        src_dir = project_root / src_dir_name
        if not src_dir.is_dir():
            continue
        for py_file in src_dir.rglob("*.py"):
            try:
                mtime = py_file.stat().st_mtime
                if mtime > newest_source_mtime:
                    newest_source_mtime = mtime
            except OSError:
                continue

    if newest_source_mtime == 0:
        return stale_warnings  # No source files found

    # Check each loaded codebase file
    for name in sorted(loaded_files):
        codebase_file = codebase_dir / f"{name}.md"
        if not codebase_file.is_file():
            stale_warnings.append(f"  {name}.md: MISSING -- run `just map-codebase` to generate")
            continue
        try:
            file_mtime = codebase_file.stat().st_mtime
        except OSError:
            continue

        if newest_source_mtime > file_mtime:
            age_hours = (newest_source_mtime - file_mtime) / 3600
            stale_warnings.append(f"  {name}.md: stale by ~{age_hours:.1f}h")

    return stale_warnings


# ---------------------------------------------------------------------------
# Context document assembly
# ---------------------------------------------------------------------------


def _build_context_md(
    epic_md_content: str,
    wiki_sections: dict[str, str],
    codebase_sections: dict[str, str],
    detected_areas: set[str],
    freshness_warnings: list[str],
) -> str:
    """Assemble the full CONTEXT.md with selective content injection."""
    assembled = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    area_list = ", ".join(sorted(detected_areas)) if detected_areas else "(none)"

    parts: list[str] = []

    # Header
    parts.append(
        f"# Epic Context\n\n"
        f"**Assembled:** {assembled}\n"
        f"**Detected Areas:** {area_list}\n\n"
        f"This document is an intermediate artefact for the plan generator. "
        f"It combines the epic description, selectively loaded architecture "
        f"documentation, and codebase context based on LLM-detected areas.\n"
    )

    # Freshness warnings
    if freshness_warnings:
        parts.append("---\n")
        parts.append(
            "> **Warning: Stale codebase files detected.** Run `just map-codebase` to refresh.\n"
        )
        for w in freshness_warnings:
            parts.append(f"> {w}")
        parts.append("")

    # Section 1: Epic description (verbatim from GitHub)
    parts.append("---\n")
    parts.append("## Epic Description\n")
    parts.append("The following is the verbatim epic body as fetched from GitHub:\n")
    parts.append(epic_md_content)

    # Section 2: Architecture (from wiki -- selected sections only)
    if wiki_sections:
        parts.append("\n---\n")
        parts.append("## Architecture (from wiki)\n")
        parts.append(
            "The following sections were selectively loaded based on "
            f"detected areas ({area_list}):\n"
        )
        for label, content in wiki_sections.items():
            parts.append(f"\n### {label}\n")
            parts.append(content.strip())
            parts.append("")

    # Section 3: Codebase Structure (selected files only)
    if codebase_sections:
        parts.append("\n---\n")
        parts.append("## Codebase Structure\n")
        parts.append("The following files were selectively loaded from `.planning/codebase/`:\n")
        for name, content in codebase_sections.items():
            parts.append(f"\n### {name}\n")
            parts.append(content.strip())
            parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assemble_context(
    epic_dir: Path,
    project_root: Path | None = None,
) -> Path:
    """Assemble context for the planner with selective content injection.

    Reads EPIC.md (must exist), performs LLM-based area detection, then
    loads only the wiki sections and codebase files relevant to the
    detected areas. Writes the assembled context to CONTEXT.md.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
        project_root: Project root directory. Defaults to epic_dir's
            grandparent-of-grandparent (i.e. 3 levels up from
            .planning/epics/E<N>/).

    Returns:
        Path to the written CONTEXT.md file.

    Raises:
        AssemblyError: If EPIC.md is missing.
    """
    if project_root is None:
        # .planning/epics/E<N> -> project root (3 levels up)
        project_root = epic_dir.resolve().parent.parent.parent

    project_root = project_root.resolve()
    wiki_dir = project_root.parent / "wiki"
    codebase_dir = project_root / ".planning" / "codebase"

    # Read inputs
    epic_md_content = _read_epic_md(epic_dir)
    epic_body = _extract_epic_body(epic_md_content)

    # LLM-based area detection
    detected_areas = detect_areas(epic_body)

    # Selective loading based on detected areas
    wiki_sections = _resolve_wiki_sections(detected_areas, wiki_dir)
    codebase_sections = _resolve_codebase_files(detected_areas, codebase_dir)

    # Freshness check
    loaded_files = set(codebase_sections.keys())
    freshness_warnings = check_freshness(project_root, codebase_dir, loaded_files)

    # Assemble the context document
    context_content = _build_context_md(
        epic_md_content=epic_md_content,
        wiki_sections=wiki_sections,
        codebase_sections=codebase_sections,
        detected_areas=detected_areas,
        freshness_warnings=freshness_warnings,
    )

    # Write output
    context_path = epic_dir / "CONTEXT.md"
    context_path.write_text(context_content, encoding="utf-8")

    return context_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Selective context assembly for epic planning")
    parser.add_argument(
        "--epic-dir",
        type=Path,
        required=True,
        help="Path to the epic directory (e.g. .planning/epics/E95/)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current working directory)",
    )
    args = parser.parse_args()

    epic_dir = args.epic_dir.resolve()
    project_root = args.project_root.resolve()

    if not epic_dir.is_dir():
        print(
            f"Error: Epic directory not found: {epic_dir}. Run ingestion first.",
            file=sys.stderr,
        )
        sys.exit(1)

    epic_md = epic_dir / "EPIC.md"
    if not epic_md.is_file():
        print(
            f"Error: EPIC.md not found at {epic_md}. Run epic ingestion first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        path = assemble_context(epic_dir, project_root)
        rel = path.relative_to(project_root)
        print(f"Assembled context at {rel}")

        # Report detected areas from the written CONTEXT.md header
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("**Detected Areas:**"):
                areas_str = line.split("**Detected Areas:**", 1)[1].strip()
                print(f"Detected areas: {areas_str}")
                break

        # Report size
        size = path.stat().st_size
        est_tokens = size // 4
        print(f"Output: {size:,d} bytes (~{est_tokens:,d} tokens)")

    except AssemblyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
