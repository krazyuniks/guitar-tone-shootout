#!/usr/bin/env python3
"""Per-story prompt builder with selective documentation loading.

Builds story-specific prompts with domain-filtered rules and a compressed
documentation index. Called by the orchestrator when constructing prompts
for story agents.

All pure Python I/O -- zero AI tokens spent.

Usage:
    python workflow/prompt_builder.py --rules-dir .claude/rules --wiki-indexes-dir .planning/wiki-indexes
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from workflow.models import CheckCriterion, ValidationCheckpoint

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Approximate chars per token (same ratio as wiki_indexer.py)
CHARS_PER_TOKEN = 4

# Check-type to domain mapping
CHECK_TYPE_TO_DOMAINS: dict[str, list[str]] = {
    "http+dom": ["frontend"],
    "browser+db": ["frontend"],
    "screenshot": ["frontend"],
    "process": ["backend"],
    "api+response": ["backend"],
    "regression": ["testing"],
    "quality": ["testing"],
}

# Path-fragment to domain mapping (applied to files_to_modify paths)
PATH_TO_DOMAINS: list[tuple[str, list[str]]] = [
    ("webapp/api/", ["backend"]),
    ("webapp/adapters/persistence/", ["backend", "database"]),
    ("webapp/services/", ["backend"]),
    ("webapp/auth/", ["backend", "security"]),
    ("frontend/astro/", ["frontend"]),
    ("tests/", ["testing"]),
    ("libs/audio/", ["audio"]),
    ("libs/video/", ["audio"]),
    ("libs/core/domain/", ["backend"]),
    ("libs/core/ports/", ["backend"]),
    ("infrastructure/", ["infrastructure"]),
    ("sources/", ["backend"]),
]

# Domain to skills mapping
DOMAIN_TO_SKILLS: dict[str, list[str]] = {
    "backend": ["gts-backend-dev", "gts-architecture"],
    "frontend": ["gts-frontend-dev"],
    "database": ["gts-architecture"],
    "testing": ["gts-testing"],
    "security": ["gts-security"],
    "audio": ["gts-architecture"],
    "infrastructure": ["docker-infra"],
}

# Domain to wiki section names mapping
# (sections from GTS-Technical-Architecture.index and domain-specific indexes)
DOMAIN_TO_WIKI_SECTIONS: dict[str, list[str]] = {
    "backend": ["api-design", "design-patterns"],
    "frontend": ["frontend"],
    "database": ["persistence", "domain-model"],
    "testing": ["testing"],
    "security": ["auth"],
    "audio": ["audio"],
    "infrastructure": ["infrastructure"],
}


# ---------------------------------------------------------------------------
# Domain derivation
# ---------------------------------------------------------------------------


def derive_story_domains(
    story: dict,
    checkpoint: ValidationCheckpoint | None = None,
) -> set[str]:
    """Derive domains from a story dict and its validation checkpoint.

    Sources:
    - checkpoint.check_type (from plan.validation_checkpoints, resolved by caller)
    - scope file paths (create + modify)

    Returns set of domain strings like {"backend", "database", "frontend"}.
    """
    domains: set[str] = set()

    # 1. Derive from validation checkpoint check_type
    if checkpoint:
        mapped = CHECK_TYPE_TO_DOMAINS.get(checkpoint.check_type, [])
        domains.update(mapped)

    # 2. Derive from scope file paths
    scope = story.get("scope", {})
    files_to_modify = scope.get("modify", []) + scope.get("create", [])
    for file_path in files_to_modify:
        for path_fragment, path_domains in PATH_TO_DOMAINS:
            if path_fragment in file_path:
                domains.update(path_domains)

    return domains


# ---------------------------------------------------------------------------
# Rules file parsing
# ---------------------------------------------------------------------------


_DOMAIN_TAG_RE = re.compile(r"^<!--\s*domains:\s*(.+?)\s*-->")


def parse_domain_tags(rules_dir: Path) -> dict[str, list[str]]:
    """Parse domain tags from all rules files.

    Returns dict mapping filename to list of domain strings.
    e.g. {"query-patterns.md": ["backend", "database"], "security.md": ["all"]}
    """
    result: dict[str, list[str]] = {}

    for rule_file in sorted(rules_dir.glob("*.md")):
        try:
            first_line = rule_file.read_text(encoding="utf-8").split("\n", 1)[0]
        except OSError:
            continue

        match = _DOMAIN_TAG_RE.match(first_line.strip())
        if match:
            tags = [t.strip() for t in match.group(1).split(",")]
            result[rule_file.name] = tags
        else:
            # No domain tag -- treat as 'all' (safe default)
            result[rule_file.name] = ["all"]

    return result


# ---------------------------------------------------------------------------
# Rules selection
# ---------------------------------------------------------------------------


def select_rules(
    domain_tags: dict[str, list[str]],
    story_domains: set[str],
) -> list[str]:
    """Select rules files matching the story's domains.

    Always includes files tagged 'all'.
    Returns sorted list of filenames.
    """
    selected: list[str] = []

    for filename, tags in domain_tags.items():
        if "all" in tags:
            selected.append(filename)
            continue
        # Include if any tag matches any story domain
        if story_domains & set(tags):
            selected.append(filename)

    return sorted(selected)


# ---------------------------------------------------------------------------
# Doc index building
# ---------------------------------------------------------------------------


def build_doc_index(
    selected_rules: list[str],
    story_domains: set[str],
    wiki_indexes_dir: Path,
) -> str:
    """Build compressed doc index string.

    Format: [GTS]|rules:{...}|skills:{...}|wiki:{...}
    """
    # Rules: strip .md extension, comma-separated
    rules_names = sorted(r.removesuffix(".md") for r in selected_rules)

    # Skills: collect from domain mapping, deduplicate
    skills: set[str] = set()
    for domain in story_domains:
        mapped = DOMAIN_TO_SKILLS.get(domain, [])
        skills.update(mapped)
    skills_sorted = sorted(skills)

    # Wiki sections: collect from domain mapping, deduplicate
    wiki_sections: set[str] = set()
    for domain in story_domains:
        mapped = DOMAIN_TO_WIKI_SECTIONS.get(domain, [])
        wiki_sections.update(mapped)
    wiki_sorted = sorted(wiki_sections)

    parts = ["[GTS]"]
    parts.append(f"rules:{{{','.join(rules_names)}}}")
    if skills_sorted:
        parts.append(f"skills:{{{','.join(skills_sorted)}}}")
    if wiki_sorted:
        parts.append(f"wiki:{{{','.join(wiki_sorted)}}}")

    return "|".join(parts)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _read_rule_content(rules_dir: Path, filename: str) -> str | None:
    """Read a rules file, returning None if unavailable."""
    path = rules_dir / filename
    if path.is_file():
        content = path.read_text(encoding="utf-8")
        # Strip the domain tag line from the content
        lines = content.split("\n", 1)
        if len(lines) > 1 and _DOMAIN_TAG_RE.match(lines[0].strip()):
            return lines[1].strip()
        return content.strip()
    return None


def build_story_prompt(
    story: dict,
    rules_dir: Path,
    wiki_indexes_dir: Path,
    checkpoint: ValidationCheckpoint | None = None,
    inline_rules: bool = False,
    epic_dir: Path | None = None,
) -> str:
    """Build the complete story prompt with selective documentation.

    The doc index lists available rules, skills, and wiki sections so the
    agent knows what documentation exists. Rules files in .claude/rules/ are
    loaded automatically by Claude Code -- they do not need to be inlined
    unless ``inline_rules=True`` is set (which exceeds the 650-token budget).

    Args:
        story: Story dict from plan.json.
        rules_dir: Path to .claude/rules/ directory.
        wiki_indexes_dir: Path to .planning/wiki-indexes/ directory.
        checkpoint: Validation checkpoint that will run after this story
            (from plan.validation_checkpoints, resolved by the caller).
        inline_rules: If True, inline rule file contents into the prompt.
        epic_dir: Path to the epic directory. If provided and EPIC_STATUS.md
            exists, a reference line is added to the prompt.

    Returns the prompt string with:
    1. Compressed doc index line (lists rules, skills, wiki sections)
    2. AGENTS.md pointer
    3. Epic status reference (if EPIC_STATUS.md exists)
    4. Optionally, inlined rules file contents (domain-filtered)
    5. Story-specific instructions
    6. Validation checkpoint criteria (if any)
    """
    # Derive domains
    story_domains = derive_story_domains(story, checkpoint)

    # Parse and select rules
    domain_tags = parse_domain_tags(rules_dir)
    selected_rules = select_rules(domain_tags, story_domains)

    # Build doc index
    doc_index = build_doc_index(selected_rules, story_domains, wiki_indexes_dir)

    # Assemble prompt parts
    parts: list[str] = []

    # 1. Doc index (single line, top of prompt)
    parts.append(doc_index)
    parts.append("")

    # 2. AGENTS.md pointer (lightweight reference)
    parts.append("Follow project conventions in AGENTS.md.")
    parts.append("")

    # 3. Epic status reference (if available)
    if epic_dir is not None:
        status_path = epic_dir / "EPIC_STATUS.md"
        if status_path.is_file():
            parts.append(f"Read `{status_path}` for epic context.")
            parts.append("")

    # 4. Optionally inline selected rules (domain-filtered)
    if inline_rules and selected_rules:
        parts.append("---")
        parts.append("## Rules")
        parts.append("")
        for filename in selected_rules:
            content = _read_rule_content(rules_dir, filename)
            if content:
                parts.append(content)
                parts.append("")

    # 5. Story-specific instructions
    parts.append("---")
    parts.append("## Story")
    parts.append("")
    parts.append(f"**ID:** {story.get('story_id', 'unknown')}")
    parts.append(f"**Name:** {story.get('name', 'unknown')}")
    parts.append(f"**Purpose:** {story.get('purpose', '')}")
    parts.append("")

    # Scope
    scope = story.get("scope", {})
    create_files = scope.get("create", [])
    modify_files = scope.get("modify", [])
    if create_files or modify_files:
        parts.append("### Scope")
        if create_files:
            parts.append("**Create:**")
            for f in create_files:
                parts.append(f"- `{f}`")
        if modify_files:
            parts.append("**Modify:**")
            for f in modify_files:
                parts.append(f"- `{f}`")
        parts.append("")

    # Implementation notes
    notes = story.get("implementation_notes", [])
    if notes:
        parts.append("### Implementation Notes")
        for note in notes:
            parts.append(f"- {note}")
        parts.append("")

    # Validation checkpoint (tells the agent what will be verified after it)
    if checkpoint:
        parts.append("### Validation Checkpoint")
        parts.append("")
        parts.append(f"After this story, a **{checkpoint.check_type}** validation will verify:")
        for check in checkpoint.checks:
            evidence = ", ".join(check.evidence_fields)
            parts.append(f"- {check.criterion} (evidence: {evidence})")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (4 chars per token)."""
    return len(text) // CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate sample prompts and print token estimates."""
    parser = argparse.ArgumentParser(
        description="Per-story prompt builder with selective documentation loading"
    )
    parser.add_argument(
        "--rules-dir",
        type=Path,
        required=True,
        help="Path to .claude/rules/ directory",
    )
    parser.add_argument(
        "--wiki-indexes-dir",
        type=Path,
        required=True,
        help="Path to .planning/wiki-indexes/ directory",
    )
    args = parser.parse_args()

    rules_dir = args.rules_dir.resolve()
    wiki_indexes_dir = args.wiki_indexes_dir.resolve()

    if not rules_dir.is_dir():
        print(f"Error: rules directory not found: {rules_dir}", file=sys.stderr)
        sys.exit(1)

    if not wiki_indexes_dir.is_dir():
        print(f"Error: wiki-indexes directory not found: {wiki_indexes_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse domain tags once
    domain_tags = parse_domain_tags(rules_dir)
    print("=== Domain Tags ===")
    for filename, tags in sorted(domain_tags.items()):
        print(f"  {filename}: {tags}")
    print()

    # Sample stories and checkpoints for testing.
    # Checkpoints live at plan level (plan.validation_checkpoints), not inside
    # stories. Each checkpoint references a story_id via after_story.
    sample_stories: dict[str, dict] = {
        "backend": {
            "story_id": "sample-backend",
            "name": "Backend API Implementation",
            "purpose": "Implement REST API endpoints for signal chains.",
            "scope": {
                "create": [],
                "modify": [
                    "apps/webapp/src/webapp/api/v1/signal_chains.py",
                    "apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain.py",
                ],
            },
            "implementation_notes": [
                "Follow existing repository patterns",
                "Use joinedload for eager loading",
            ],
        },
        "frontend": {
            "story_id": "sample-frontend",
            "name": "Frontend Page Implementation",
            "purpose": "Build the gear library browsing page.",
            "scope": {
                "create": [],
                "modify": [
                    "frontend/astro/src/pages/gear/index.html.ts",
                ],
            },
            "implementation_notes": [
                "Use Astro SSG pattern",
                "Add data-testid attributes",
            ],
        },
        "full-stack": {
            "story_id": "sample-full-stack",
            "name": "Full-Stack Feature",
            "purpose": "DI track upload with frontend form and backend processing.",
            "scope": {
                "create": ["tests/regression/test_di_tracks.py"],
                "modify": [
                    "apps/webapp/src/webapp/api/v1/di_tracks.py",
                    "apps/webapp/src/webapp/adapters/persistence/repositories/di_track.py",
                    "frontend/astro/src/pages/library/di-tracks.html.ts",
                ],
            },
            "implementation_notes": [
                "Upload form with HTMX",
                "Backend file validation",
                "Write regression tests",
            ],
        },
    }

    # Checkpoints keyed by story_id (mirrors plan.validation_checkpoints)
    sample_checkpoints: dict[str, ValidationCheckpoint] = {
        "sample-backend": ValidationCheckpoint(
            after_story="sample-backend",
            check_type="api+response",
            checks=[CheckCriterion(criterion="API returns 200", evidence_fields=["status_code"])],
        ),
        "sample-frontend": ValidationCheckpoint(
            after_story="sample-frontend",
            check_type="http+dom",
            checks=[CheckCriterion(criterion="Page renders", evidence_fields=["dom_element"])],
        ),
        "sample-full-stack": ValidationCheckpoint(
            after_story="sample-full-stack",
            check_type="regression",
            checks=[CheckCriterion(criterion="Tests pass", evidence_fields=["test_output"])],
        ),
    }

    # Generate and report for each sample
    all_tagged_files = {fn for fn, tags in domain_tags.items() if "all" in tags}

    for label, story in sample_stories.items():
        print(f"=== {label.upper()} Story ===")
        print()

        story_id = story["story_id"]
        cp = sample_checkpoints.get(story_id)

        # Derive domains
        domains = derive_story_domains(story, cp)
        print(f"  Domains: {sorted(domains)}")

        # Select rules
        selected = select_rules(domain_tags, domains)
        print(f"  Selected rules ({len(selected)}):")
        for r in selected:
            marker = " [all]" if r in all_tagged_files else ""
            print(f"    - {r}{marker}")

        # Verify all-tagged rules are present
        missing_all = all_tagged_files - set(selected)
        if missing_all:
            print(f"  WARNING: Missing 'all'-tagged rules: {sorted(missing_all)}")
        else:
            print("  All 'all'-tagged rules present: YES")

        # Check domain-specific rules absent from non-matching prompts
        for fn, tags in domain_tags.items():
            if "all" in tags:
                continue
            if fn in selected and not (domains & set(tags)):
                print(
                    f"  WARNING: {fn} selected but domains {tags} don't match story domains {sorted(domains)}"
                )

        # Build doc index
        doc_index = build_doc_index(selected, domains, wiki_indexes_dir)
        print(f"  Doc index: {doc_index}")

        # Build prompt (default: index-only mode, within 650-token budget)
        prompt = build_story_prompt(story, rules_dir, wiki_indexes_dir, checkpoint=cp)
        tokens = estimate_tokens(prompt)
        print(f"  Prompt size (index-only): {len(prompt):,d} chars (~{tokens:,d} tokens)")

        # Measure doc overhead (everything except story section)
        story_marker = "---\n## Story"
        story_idx = prompt.find(story_marker)
        if story_idx >= 0:
            doc_overhead = prompt[:story_idx]
            doc_tokens = estimate_tokens(doc_overhead)
            budget_status = "WITHIN" if doc_tokens <= 650 else "EXCEEDS"
            print(
                f"  Doc overhead (index-only): ~{doc_tokens:,d} tokens ({budget_status} 650-token target)"
            )

        # Also show inlined-rules mode for comparison
        prompt_inlined = build_story_prompt(
            story, rules_dir, wiki_indexes_dir, checkpoint=cp, inline_rules=True
        )
        tokens_inlined = estimate_tokens(prompt_inlined)
        print(
            f"  Prompt size (rules inlined): {len(prompt_inlined):,d} chars (~{tokens_inlined:,d} tokens)"
        )
        print()

    # Verification summary
    print("=== Verification Summary ===")
    print()

    # 1. Backend story should NOT have frontend-standards.md
    backend_cp = sample_checkpoints.get("sample-backend")
    backend_domains = derive_story_domains(sample_stories["backend"], backend_cp)
    backend_rules = select_rules(domain_tags, backend_domains)
    if "frontend-standards.md" in backend_rules:
        print("  FAIL: Backend story includes frontend-standards.md")
    else:
        print("  PASS: Backend story excludes frontend-standards.md")

    # 2. Frontend story should NOT have query-patterns.md
    frontend_cp = sample_checkpoints.get("sample-frontend")
    frontend_domains = derive_story_domains(sample_stories["frontend"], frontend_cp)
    frontend_rules = select_rules(domain_tags, frontend_domains)
    if "query-patterns.md" in frontend_rules:
        print("  FAIL: Frontend story includes query-patterns.md")
    else:
        print("  PASS: Frontend story excludes query-patterns.md")

    # 3. Full-stack story should include both
    fullstack_cp = sample_checkpoints.get("sample-full-stack")
    fullstack_domains = derive_story_domains(sample_stories["full-stack"], fullstack_cp)
    fullstack_rules = select_rules(domain_tags, fullstack_domains)
    has_frontend = "frontend-standards.md" in fullstack_rules
    has_backend = "query-patterns.md" in fullstack_rules
    if has_frontend and has_backend:
        print("  PASS: Full-stack story includes both frontend-standards.md and query-patterns.md")
    else:
        missing = []
        if not has_frontend:
            missing.append("frontend-standards.md")
        if not has_backend:
            missing.append("query-patterns.md")
        print(f"  FAIL: Full-stack story missing: {missing}")

    # 4. All-tagged rules in every prompt
    for label, story in sample_stories.items():
        story_id = story["story_id"]
        cp = sample_checkpoints.get(story_id)
        domains = derive_story_domains(story, cp)
        selected = set(select_rules(domain_tags, domains))
        missing = all_tagged_files - selected
        if missing:
            print(f"  FAIL: {label} story missing 'all'-tagged rules: {sorted(missing)}")
        else:
            print(f"  PASS: {label} story has all 'all'-tagged rules")


if __name__ == "__main__":
    main()
