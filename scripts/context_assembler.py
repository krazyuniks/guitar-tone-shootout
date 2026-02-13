"""Deterministic context assembly for the V2 epic planner.

Reads EPIC.md, wiki sections, codebase structure files, and performs
keyword-based area detection — all pure Python I/O with zero AI tokens.
Outputs CONTEXT.md as the input for the plan generator.

Usage:
    python scripts/context_assembler.py <epic_number>
"""

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
CODEBASE_DIR = PROJECT_ROOT / ".planning" / "codebase"
WIKI_DIR = PROJECT_ROOT.parent / "wiki"


class AssemblyError(Exception):
    """Raised when context assembly fails."""


# ---------------------------------------------------------------------------
# Keyword-to-area mapping
# ---------------------------------------------------------------------------
# Extracted from .claude/skills/epic/references/gray-areas.md
# Each entry maps a set of keywords to the area IDs they suggest.

KEYWORD_AREA_MAP: list[tuple[list[str], list[str]]] = [
    # GTS domain-specific patterns
    (
        ["signal chain", "chain", "block", "processing"],
        ["signal_chain", "audio_processing", "gear_model"],
    ),
    (
        ["amp", "pedal", "ir", "cabinet", "capture", "nam"],
        ["gear_model", "signal_chain", "dual_database"],
    ),
    (
        ["shootout", "compare", "comparison", "a/b"],
        ["signal_chain", "audio_processing", "job_processing", "frontend_layers"],
    ),
    (
        ["gear", "library", "collection", "my gear"],
        ["gear_model", "frontend_layers", "data_model"],
    ),
    (
        ["sync", "t3k", "tone3000", "source"],
        ["dual_database", "job_processing", "gear_model"],
    ),
    (
        ["process", "render", "audio", "video"],
        ["audio_processing", "job_processing", "signal_chain"],
    ),
    # Standard patterns
    (
        ["form", "submit", "input", "create", "add"],
        ["data_model", "api_contract", "security", "frontend_layers"],
    ),
    (
        ["notification", "alert", "email"],
        ["job_processing"],
    ),
    (
        ["upload", "file", "di track", "recording"],
        ["data_model", "api_contract", "security", "job_processing"],
    ),
    (
        ["search", "filter", "browse", "list"],
        ["data_model", "api_contract", "frontend_layers"],
    ),
    (
        ["auth", "login", "oauth", "session"],
        ["security", "data_model", "api_contract"],
    ),
    (
        ["page", "template", "ui", "display", "show"],
        ["frontend_layers", "api_contract"],
    ),
]

# Required area mappings — if feature mentions these, always include the areas
REQUIRED_AREA_MAP: list[tuple[list[str], list[str]]] = [
    (
        ["signal chain", "block", "amp", "ir"],
        ["signal_chain", "gear_model"],
    ),
    (
        ["processing", "render", "audio"],
        ["audio_processing", "job_processing"],
    ),
    (
        ["sync", "t3k", "source"],
        ["dual_database"],
    ),
    (
        ["page", "template", "form"],
        ["frontend_layers"],
    ),
    (
        ["background", "job", "queue"],
        ["job_processing"],
    ),
]

# Area definitions from gray-areas.md
AREA_DEFINITIONS: dict[str, dict[str, str]] = {
    "signal_chain": {
        "name": "Signal Chain",
        "description": "Block types, ordering, validation rules",
        "questions": "HEAD vs FULL_RIG, IR requirements, loop effects",
    },
    "gear_model": {
        "name": "Gear Model",
        "description": "Unified gear, sources, sync records",
        "questions": "Source attribution, GearModel files, UserGear",
    },
    "dual_database": {
        "name": "Dual Database",
        "description": "gts_core vs gts_t3k_source boundaries",
        "questions": "Which database, worker access, pgmq messages",
    },
    "frontend_layers": {
        "name": "Frontend Layers",
        "description": "Astro SSG vs Jinja2 SSR vs HTMX fragments",
        "questions": "Page type, React island, navigation patterns",
    },
    "job_processing": {
        "name": "Jobs/Queues",
        "description": "TaskIQ jobs, pgmq consumers, parent/child",
        "questions": "Retry strategy, progress reporting, Redis locks",
    },
    "audio_processing": {
        "name": "Audio Processing",
        "description": "NAM, IR, loudness normalization",
        "questions": "libs/audio vs apps/worker, processing pipeline",
    },
    "data_model": {
        "name": "Data Model",
        "description": "Tables, columns, relations (SQLAlchemy ORM)",
        "questions": "Primary entity, lifecycle, indexes",
    },
    "orm_patterns": {
        "name": "ORM Patterns",
        "description": "Repository pattern, transactions",
        "questions": "Reference repository, eager/lazy loading",
    },
    "api_contract": {
        "name": "API Contract",
        "description": "Endpoints, Pydantic schemas, errors",
        "questions": "REST vs HTML endpoints, validation, pagination",
    },
    "security": {
        "name": "Security",
        "description": "Auth, session cookies, ownership checks",
        "questions": "Authentication required, CurrentUser, rate limiting",
    },
    "testing": {
        "name": "Testing Strategy",
        "description": "Unit/integration/E2E boundaries, no-mock policy",
        "questions": "What to test at each level, all real services",
    },
}

# Question bank from question-bank.md — area-specific questions for scope discussion
AREA_QUESTIONS: dict[str, list[str]] = {
    "signal_chain": [
        "Does this feature involve signal chains?",
        "Which block types are affected? (amp, IR, pedal, built-in)",
        "HEAD vs FULL_RIG considerations? (IR required vs forbidden)",
        "Loop effects allowed? (not with FULL_RIG)",
        "Block ordering constraints?",
        "Permutation support needed? (SignalChainGroup)",
    ],
    "gear_model": [
        "Does this feature involve gear?",
        "Unified Gear model or source-specific?",
        "GearModel files involved? (NAM, IR)",
        "Source attribution needed?",
        "User-uploaded (community) or synced from source?",
        "UserGear library implications?",
    ],
    "dual_database": [
        "Which database is this for? (gts_core or gts_t3k_source)",
        "If source data, is worker the access point?",
        "pgmq messages involved?",
        "Sync records needed?",
        "Cross-database implications?",
    ],
    "frontend_layers": [
        "Is this a static page (Astro SSG)?",
        "Is this a dynamic page (Jinja2 SSR)?",
        "Does it need HTMX fragments?",
        "Is it the SignalChainBuilder (React)?",
        "Design tokens from Astro CSS?",
    ],
    "job_processing": [
        "Does this trigger background jobs?",
        "TaskIQ job or pgmq consumer?",
        "Parent/child job hierarchy? (like SHOOTOUT)",
        "Retry strategy and max attempts?",
        "Progress reporting (WebSocket for user jobs)?",
        "Redis locks needed?",
    ],
    "audio_processing": [
        "Does this involve audio processing?",
        "NAM model loading?",
        "IR convolution?",
        "Loudness normalization?",
        "libs/audio or apps/worker?",
    ],
    "data_model": [
        "What's the primary entity?",
        "What fields are required vs optional?",
        "What's the status/lifecycle?",
        "Relations to existing tables in gts_core?",
        "Indexes or constraints needed?",
        "Soft delete or hard delete?",
    ],
    "orm_patterns": [
        "Follow existing repository pattern?",
        "Which existing repository to reference?",
        "Eager or lazy loading for relations?",
        "Transaction boundaries (service owns)?",
    ],
    "api_contract": [
        "REST endpoint path? (/api/v1/...)",
        "HTML endpoint path? (/api/v1/html/...)",
        "Pydantic request/response schemas?",
        "Validation error format?",
        "Pagination approach (offset or cursor)?",
    ],
    "security": [
        "Does endpoint require authentication?",
        "CurrentUser dependency?",
        "Ownership check (user_id match)?",
        "Return 404 for unauthorised (not 403)?",
        "Rate limiting?",
    ],
    "testing": [
        "What pure functions need testing? (tests/unit/)",
        "What API flows need testing? (tests/integration/)",
        "What user journeys are critical? (tests/e2e/python/)",
        "Playwright page interactions?",
        "Three-layer validation (UI > DOM > Database)?",
    ],
}


# ---------------------------------------------------------------------------
# Keyword scanning
# ---------------------------------------------------------------------------


def scan_keywords(text: str) -> set[str]:
    """Scan text for keywords and return matching area IDs.

    Performs case-insensitive substring matching against the keyword-to-area
    mapping tables.  Returns a deduplicated set of area IDs.
    """
    text_lower = text.lower()
    matched_areas: set[str] = set()

    for keywords, areas in KEYWORD_AREA_MAP:
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched_areas.update(areas)
                break  # One keyword match is enough for this group

    # Apply required area rules (stricter — always include these)
    for keywords, areas in REQUIRED_AREA_MAP:
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched_areas.update(areas)
                break

    return matched_areas


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
            f"python scripts/epic_ingest.py <number>"
        )
    return content


def _extract_epic_body(epic_md_content: str) -> str:
    """Extract the body (after YAML frontmatter) from EPIC.md."""
    # YAML frontmatter is delimited by --- ... ---
    match = re.match(r"^---\n.*?\n---\n(.*)", epic_md_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return epic_md_content.strip()


def _read_wiki_sections() -> dict[str, str]:
    """Read relevant wiki markdown files.

    Returns a dict mapping filename (without extension) to content.
    Only reads files that exist.
    """
    wiki_files = [
        "GTS-Technical-Architecture",
        "Frontend-Architecture",
        "Audio-Processing",
    ]
    sections: dict[str, str] = {}
    for name in wiki_files:
        path = WIKI_DIR / f"{name}.md"
        content = _read_file_safe(path)
        if content is not None:
            sections[name] = content
    return sections


def _read_codebase_files() -> dict[str, str]:
    """Read all .planning/codebase/ markdown files.

    Returns a dict mapping filename (without extension) to content.
    Expected files: STRUCTURE, ARCHITECTURE, STACK, CONVENTIONS,
    INTEGRATIONS, TESTING, CONCERNS.
    """
    codebase_files = [
        "STRUCTURE",
        "ARCHITECTURE",
        "STACK",
        "CONVENTIONS",
        "INTEGRATIONS",
        "TESTING",
        "CONCERNS",
    ]
    sections: dict[str, str] = {}
    for name in codebase_files:
        path = CODEBASE_DIR / f"{name}.md"
        content = _read_file_safe(path)
        if content is not None:
            sections[name] = content
    return sections


# ---------------------------------------------------------------------------
# Context document assembly
# ---------------------------------------------------------------------------


def _build_detected_areas_section(areas: set[str]) -> str:
    """Build the detected areas section with definitions and questions."""
    if not areas:
        return (
            "## Detected Architecture Areas\n\n"
            "No specific architecture areas detected from keywords. "
            "The planner should determine relevant areas from the epic content.\n"
        )

    lines = ["## Detected Architecture Areas\n"]
    lines.append(
        "Based on keyword analysis of the epic body, the following "
        "architecture areas are relevant:\n"
    )

    sorted_areas = sorted(areas)
    for area_id in sorted_areas:
        defn = AREA_DEFINITIONS.get(area_id)
        if defn is None:
            continue
        lines.append(f"### {defn['name']} (`{area_id}`)\n")
        lines.append(f"**Description:** {defn['description']}\n")
        lines.append(f"**Key questions:** {defn['questions']}\n")

        questions = AREA_QUESTIONS.get(area_id, [])
        if questions:
            lines.append("**Scope discussion questions:**\n")
            for q in questions:
                lines.append(f"- {q}")
            lines.append("")

    return "\n".join(lines)


def _build_context_md(
    epic_md_content: str,
    wiki_sections: dict[str, str],
    codebase_sections: dict[str, str],
    detected_areas: set[str],
) -> str:
    """Assemble the full CONTEXT.md content."""
    assembled = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    parts: list[str] = []

    # Header
    parts.append(
        f"# Epic Context\n\n"
        f"**Assembled:** {assembled}\n\n"
        f"This document is an intermediate artefact for the plan generator. "
        f"It combines the epic description, codebase context, architecture "
        f"documentation, and detected architecture areas into a single "
        f"reference. Zero AI tokens were spent producing this file.\n"
    )

    # Section 1: Epic description (verbatim from GitHub)
    parts.append("---\n")
    parts.append("## Epic Description\n")
    parts.append("The following is the verbatim epic body as fetched from GitHub:\n")
    parts.append(epic_md_content)

    # Section 2: Detected architecture areas (from keyword scan)
    parts.append("\n---\n")
    parts.append(_build_detected_areas_section(detected_areas))

    # Section 3: Codebase structure files
    if codebase_sections:
        parts.append("\n---\n")
        parts.append("## Codebase Context\n")
        parts.append("The following sections are from `.planning/codebase/` analysis files:\n")
        for name, content in codebase_sections.items():
            parts.append(f"\n### {name}\n")
            parts.append(content.strip())
            parts.append("")

    # Section 4: Wiki documentation
    if wiki_sections:
        parts.append("\n---\n")
        parts.append("## Architecture Documentation\n")
        parts.append("The following sections are from the project wiki:\n")
        for name, content in wiki_sections.items():
            parts.append(f"\n### {name}\n")
            parts.append(content.strip())
            parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assemble_context(epic_dir: Path) -> Path:
    """Assemble context for the planner from all available sources.

    Reads EPIC.md (must exist), wiki sections, codebase structure files,
    and performs keyword scanning to detect relevant architecture areas.
    Writes the assembled context to CONTEXT.md in the epic directory.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).

    Returns:
        Path to the written CONTEXT.md file.

    Raises:
        AssemblyError: If EPIC.md is missing.
    """
    # Read inputs
    epic_md_content = _read_epic_md(epic_dir)
    epic_body = _extract_epic_body(epic_md_content)
    wiki_sections = _read_wiki_sections()
    codebase_sections = _read_codebase_files()

    # Keyword scanning on the epic body
    detected_areas = scan_keywords(epic_body)

    # Assemble the context document
    context_content = _build_context_md(
        epic_md_content=epic_md_content,
        wiki_sections=wiki_sections,
        codebase_sections=codebase_sections,
        detected_areas=detected_areas,
    )

    # Write output
    context_path = epic_dir / "CONTEXT.md"
    context_path.write_text(context_content, encoding="utf-8")

    return context_path


def main() -> None:
    """CLI entry point: python scripts/context_assembler.py <epic_number>."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <epic_number>", file=sys.stderr)
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(
            f"Error: epic_number must be an integer, got: {sys.argv[1]}",
            file=sys.stderr,
        )
        sys.exit(1)

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(
            f"Error: Epic directory not found: {epic_dir}. "
            f"Run ingestion first: python scripts/epic_ingest.py {epic_number}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        path = assemble_context(epic_dir)
        print(f"Assembled context for epic #{epic_number} at {path.relative_to(PROJECT_ROOT)}")
    except AssemblyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
