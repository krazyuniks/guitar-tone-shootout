"""Extract codebase facts from .planning/codebase/ files into FACTS.md.

Reads four pre-built markdown files (SCHEMA.md, ENDPOINTS.md, STRUCTURE.md,
IMPORTS.md) and produces a compact FACTS.md reference for story agents.

Usage:
    python -m workflow.codebase_facts_extractor
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_tables(text: str) -> dict[str, list[str]]:
    """Extract table names from SCHEMA.md and group by BC prefix.

    Recognises:
    - Markdown headers: ## tablename or ### tablename
    - Bold names: **tablename**
    - CREATE TABLE tablename
    - table_name = "tablename"
    """
    _table_name = r"[a-z][a-z0-9_]+"
    patterns = [
        re.compile(r"^#{2,3}\s+(" + _table_name + r")", re.MULTILINE | re.IGNORECASE),
        re.compile(r"\*\*(" + _table_name + r")\*\*", re.IGNORECASE),
        re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(" + _table_name + r")",
            re.IGNORECASE,
        ),
        re.compile(
            r"table_name\s*=\s*[\"'](" + _table_name + r")[\"']",
            re.IGNORECASE,
        ),
    ]

    tables: set[str] = set()
    for pattern in patterns:
        for m in pattern.finditer(text):
            name = m.group(1).lower()
            # Must contain an underscore to look like a BC-prefixed table name
            if "_" in name:
                tables.add(name)

    # Group by prefix (first segment before first underscore)
    grouped: dict[str, list[str]] = {}
    for table in sorted(tables):
        prefix = table.split("_")[0]
        grouped.setdefault(prefix, []).append(table)

    return grouped


def _extract_endpoints(text: str) -> list[str]:
    """Extract HTTP method + path pairs from ENDPOINTS.md.

    Recognises:
    - Lines like: GET /api/...
    - Markdown table rows with method and path columns
    """
    endpoint_pattern = re.compile(
        r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s|,;`\"'<>]+)",
        re.IGNORECASE,
    )

    seen: set[str] = set()
    endpoints: list[str] = []
    for m in endpoint_pattern.finditer(text):
        method = m.group(1).upper()
        path = m.group(2).rstrip(")")
        entry = f"{method} {path}"
        if entry not in seen:
            seen.add(entry)
            endpoints.append(entry)

    return sorted(endpoints)


def _extract_module_structure(text: str) -> list[str]:
    """Extract top-level module paths from STRUCTURE.md.

    Keeps paths that:
    - Contain at least one "/"
    - Do not start with "#"
    - Have depth <= 3 (at most two "/" after any prefix)
    """
    seen: set[str] = set()
    paths: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        # Skip comments, blank lines, headings
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue

        # Extract something that looks like a path (contains /)
        # Allow leading list markers like "- " or "* "
        path_candidate = re.sub(r"^[-*+]\s+", "", stripped)
        path_candidate = path_candidate.strip("`|> \t")

        if "/" not in path_candidate:
            continue

        # Only keep paths, not sentences
        if " " in path_candidate:
            continue

        # Limit depth: count "/" separators
        depth = path_candidate.count("/")
        if depth > 3:
            continue

        if path_candidate not in seen:
            seen.add(path_candidate)
            paths.append(path_candidate)

    return sorted(paths)


def _extract_bc_dependencies(text: str) -> list[str]:
    """Extract BC dependency mappings from IMPORTS.md.

    Recognises:
    - module imports dependency
    - module -> dependency
    - module: [dep1, dep2]
    """
    seen: set[str] = set()
    deps: list[str] = []

    # Pattern: "module -> dependency" or "module imports dependency"
    arrow_pattern = re.compile(
        r"([a-z][a-z0-9_-]+)\s+(?:->|imports)\s+([a-z][a-z0-9_-]+)",
        re.IGNORECASE,
    )
    # Pattern: "module: [dep1, dep2, ...]"
    list_pattern = re.compile(
        r"([a-z][a-z0-9_-]+)\s*:\s*\[([^\]]+)\]",
        re.IGNORECASE,
    )

    for m in arrow_pattern.finditer(text):
        src = m.group(1).lower()
        dst = m.group(2).lower()
        entry = f"{src} -> {dst}"
        if entry not in seen:
            seen.add(entry)
            deps.append(entry)

    for m in list_pattern.finditer(text):
        src = m.group(1).lower()
        for dst_raw in m.group(2).split(","):
            dst = dst_raw.strip().lower()
            if dst:
                entry = f"{src} -> {dst}"
                if entry not in seen:
                    seen.add(entry)
                    deps.append(entry)

    return sorted(deps)


# ---------------------------------------------------------------------------
# Main interface
# ---------------------------------------------------------------------------


def extract_facts(
    codebase_dir: Path,
    output_path: Path | None = None,
) -> Path:
    """Extract codebase facts from .planning/codebase/ files into FACTS.md.

    Args:
        codebase_dir: Path to .planning/codebase/ directory.
        output_path: Where to write FACTS.md. Defaults to codebase_dir/FACTS.md.

    Returns:
        Path to the generated FACTS.md.
    """
    if output_path is None:
        output_path = codebase_dir / "FACTS.md"

    required = {
        "SCHEMA.md": codebase_dir / "SCHEMA.md",
        "ENDPOINTS.md": codebase_dir / "ENDPOINTS.md",
        "STRUCTURE.md": codebase_dir / "STRUCTURE.md",
        "IMPORTS.md": codebase_dir / "IMPORTS.md",
    }

    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing codebase files: {', '.join(sorted(missing))}. "
            "Run `just map-codebase` to generate them."
        )

    sections: list[str] = ["# Codebase Facts", ""]

    # Tables from SCHEMA.md
    text = required["SCHEMA.md"].read_text(encoding="utf-8")
    grouped = _extract_tables(text)
    if grouped:
        sections.append("## Tables")
        sections.append("")
        for prefix in sorted(grouped):
            sections.append(f"### {prefix}")
            for table in grouped[prefix]:
                sections.append(f"- {table}")
            sections.append("")

    # Endpoints from ENDPOINTS.md
    text = required["ENDPOINTS.md"].read_text(encoding="utf-8")
    endpoints = _extract_endpoints(text)
    if endpoints:
        sections.append("## Endpoints")
        sections.append("")
        for ep in endpoints:
            sections.append(f"- {ep}")
        sections.append("")

    # Module structure from STRUCTURE.md
    text = required["STRUCTURE.md"].read_text(encoding="utf-8")
    paths = _extract_module_structure(text)
    if paths:
        sections.append("## Module Structure")
        sections.append("")
        for p in paths:
            sections.append(f"- {p}")
        sections.append("")

    # BC dependencies from IMPORTS.md
    text = required["IMPORTS.md"].read_text(encoding="utf-8")
    bc_deps = _extract_bc_dependencies(text)
    if bc_deps:
        sections.append("## BC Dependencies")
        sections.append("")
        for dep in bc_deps:
            sections.append(f"- {dep}")
        sections.append("")

    content = "\n".join(sections)
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent


def main() -> None:
    """CLI: generate .planning/codebase/FACTS.md from the four source files."""
    project_root = _find_project_root()
    codebase_dir = project_root / ".planning" / "codebase"

    if not codebase_dir.is_dir():
        print(
            f"Error: {codebase_dir} does not exist. Run `just map-codebase` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        output_path = extract_facts(codebase_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"FACTS.md written to {output_path}")


if __name__ == "__main__":
    main()
