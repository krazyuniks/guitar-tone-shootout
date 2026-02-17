#!/usr/bin/env python3
"""Generate header-only indexes for wiki markdown files.

Scans ../wiki/*.md files and produces compact pipe-delimited indexes
with section names, line ranges, and approximate token counts.

Files with <!-- CONTEXT:name --> markers use marker names directly.
Files without markers use sanitised header names.

Output is written to .planning/wiki-indexes/ as one index file per
wiki markdown file.

Uses only Python stdlib. No external dependencies.

Usage:
    python workflow/wiki_indexer.py
    python workflow/wiki_indexer.py --wiki-dir /path/to/wiki
    python workflow/wiki_indexer.py --output-dir /path/to/output
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Approximate token-to-character ratio for English/code markdown.
# GPT-family tokenisers average ~4 chars per token for mixed prose/code.
CHARS_PER_TOKEN = 4

# Pattern matching <!-- CONTEXT:name --> markers
CONTEXT_OPEN_RE = re.compile(r"^<!--\s*CONTEXT:(\S+)\s*-->$")
CONTEXT_CLOSE_RE = re.compile(r"^<!--\s*/CONTEXT\s*-->$")

# Pattern matching markdown headers (# through ###)
HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$")


def _sanitise_header(text: str) -> str:
    """Convert a header string to a kebab-case section identifier.

    Examples:
        "## Build System" -> "build-system"
        "### Post-Build CSS Injection" -> "post-build-css-injection"
        "# Audio Processing" -> "audio-processing"
    """
    # Strip any trailing anchor links or markup
    text = text.strip()
    # Remove backticks, parentheses, and other punctuation
    text = re.sub(r"[`()\[\]{}*_~#]", "", text)
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric runs with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def _estimate_tokens(char_count: int) -> int:
    """Estimate token count from character count."""
    return char_count // CHARS_PER_TOKEN


def _round_tokens(count: int) -> int:
    """Round token count to nearest 50 for compact display."""
    if count < 50:
        return count
    return round(count / 50) * 50


# ---------------------------------------------------------------------------
# CONTEXT-marker extraction (for files like GTS-Technical-Architecture.md)
# ---------------------------------------------------------------------------


def _extract_context_sections(lines: list[str]) -> list[dict] | None:
    """Extract sections using <!-- CONTEXT:name --> markers.

    Skips markers inside fenced code blocks (``` or ~~~).
    Returns a list of section dicts, or None if no CONTEXT markers found.
    Each dict has: name, start_line, end_line, char_count.
    Line numbers are 1-based.
    """
    sections: list[dict] = []
    current_name: str | None = None
    current_start: int = 0
    current_chars: int = 0
    in_code_block: bool = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track fenced code blocks
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            if current_name is not None:
                current_chars += len(line) + 1
            continue

        # Skip markers inside code blocks
        if in_code_block:
            if current_name is not None:
                current_chars += len(line) + 1
            continue

        open_match = CONTEXT_OPEN_RE.match(stripped)
        if open_match:
            current_name = open_match.group(1)
            current_start = i + 1  # 1-based, marker line itself
            current_chars = 0
            continue

        close_match = CONTEXT_CLOSE_RE.match(stripped)
        if close_match and current_name is not None:
            sections.append(
                {
                    "name": current_name,
                    "start_line": current_start,
                    "end_line": i + 1,  # 1-based, includes close marker
                    "char_count": current_chars,
                }
            )
            current_name = None
            continue

        if current_name is not None:
            current_chars += len(line) + 1  # +1 for newline

    return sections if sections else None


# ---------------------------------------------------------------------------
# Header-based extraction (for files without CONTEXT markers)
# ---------------------------------------------------------------------------


def _extract_header_sections(lines: list[str]) -> list[dict]:
    """Extract sections based on markdown ## headers.

    Uses ## (h2) headers as primary section boundaries.
    Skips headers inside fenced code blocks (``` or ~~~).
    Returns a list of section dicts with: name, start_line, end_line, char_count.
    Line numbers are 1-based.
    """
    sections: list[dict] = []
    current_name: str | None = None
    current_start: int = 0
    current_chars: int = 0
    in_code_block: bool = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track fenced code blocks to avoid treating comments as headers
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            if current_name is not None:
                current_chars += len(line) + 1
            continue

        if in_code_block:
            if current_name is not None:
                current_chars += len(line) + 1
            continue

        header_match = HEADER_RE.match(stripped)

        if header_match:
            level = len(header_match.group(1))
            header_text = header_match.group(2)

            # Only split on h2 (##) headers as section boundaries.
            # h1 is the document title; h3+ are subsections within a section.
            if level <= 2:
                # Close previous section
                if current_name is not None:
                    sections.append(
                        {
                            "name": current_name,
                            "start_line": current_start,
                            "end_line": i,  # 1-based, line before this header
                            "char_count": current_chars,
                        }
                    )

                # Start new section
                if level == 1:
                    # h1 titles become preamble (document title + intro)
                    current_name = _sanitise_header(header_text)
                else:
                    current_name = _sanitise_header(header_text)
                current_start = i + 1  # 1-based
                current_chars = len(line) + 1
                continue

        if current_name is not None:
            current_chars += len(line) + 1  # +1 for newline

    # Close final section
    if current_name is not None:
        sections.append(
            {
                "name": current_name,
                "start_line": current_start,
                "end_line": len(lines),
                "char_count": current_chars,
            }
        )

    return sections


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------


def _build_index(wiki_file: Path) -> str | None:
    """Build a pipe-delimited index string for a single wiki file.

    Returns the index string, or None if the file has no sections.
    """
    text = wiki_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines:
        return None

    # Try CONTEXT markers first
    sections = _extract_context_sections(lines)

    # Fall back to header-based extraction
    if sections is None:
        sections = _extract_header_sections(lines)

    if not sections:
        return None

    # Build pipe-delimited entries
    entries: list[str] = []
    for section in sections:
        tokens = _round_tokens(_estimate_tokens(section["char_count"]))
        entry = f"{section['name']}:L{section['start_line']}-L{section['end_line']}:~{tokens}tok"
        entries.append(entry)

    return "|".join(entries)


def index_wiki(wiki_dir: Path, output_dir: Path) -> list[Path]:
    """Generate indexes for all markdown files in wiki_dir.

    Returns list of generated output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    wiki_files = sorted(wiki_dir.glob("*.md"))
    if not wiki_files:
        print(f"Warning: no .md files found in {wiki_dir}", file=sys.stderr)
        return []

    generated: list[Path] = []

    for wiki_file in wiki_files:
        index_line = _build_index(wiki_file)
        if index_line is None:
            print(f"  {wiki_file.name:45s} (no sections)")
            continue

        # Write one index file per wiki file
        out_path = output_dir / f"{wiki_file.stem}.index"
        content = f"# {wiki_file.name}\n{index_line}\n"
        out_path.write_text(content, encoding="utf-8")
        generated.append(out_path)

        # Count sections for summary
        section_count = index_line.count("|") + 1
        print(f"  {wiki_file.name:45s} {section_count:>3d} sections -> {out_path.name}")

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate header-only indexes for wiki markdown files"
    )
    parser.add_argument(
        "--wiki-dir",
        type=Path,
        default=None,
        help="Wiki directory (default: ../wiki/ relative to project root)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: .planning/wiki-indexes/)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current working directory)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    wiki_dir = (args.wiki_dir or project_root.parent / "wiki").resolve()
    output_dir = (args.output_dir or project_root / ".planning" / "wiki-indexes").resolve()

    if not wiki_dir.is_dir():
        print(f"Error: wiki directory does not exist: {wiki_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Wiki dir:    {wiki_dir}")
    print(f"Output dir:  {output_dir}")
    print()

    generated = index_wiki(wiki_dir, output_dir)

    print()
    print(f"Generated {len(generated)} index files in {output_dir}")


if __name__ == "__main__":
    main()
