"""Deterministic repo-facts builder for epic planning.

Builds `.planning/epics/E<N>/repo_facts.json` from the epic contract plus
live repo inspection. Optional `.planning/codebase/` artefacts are used only
as non-authoritative hints to widen candidate discovery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from workflow.artifacts import (
    EpicArtifact,
    RepoFactArtifact,
    RepoFactEvidenceArtifact,
    RepoFactsArtifact,
)
from workflow.codebase_facts_extractor import load_optional_codebase_hints

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SEARCHABLE_SUFFIXES = {
    ".css",
    ".html",
    ".jinja",
    ".jinja2",
    ".js",
    ".json",
    ".jsonl",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
SEARCHABLE_FILENAMES = {
    "Dockerfile",
    "Justfile",
    "justfile",
    "pyproject.toml",
}
SKIP_TOP_LEVEL_DIR_NAMES = {
    ".agents",
    ".claude",
    ".serena",
}
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
STOPWORDS = {
    "about",
    "after",
    "agent",
    "agents",
    "allow",
    "automatic",
    "before",
    "build",
    "comment",
    "comments",
    "compile",
    "concrete",
    "consume",
    "consumes",
    "contract",
    "current",
    "design",
    "direct",
    "exactly",
    "focus",
    "generation",
    "human",
    "implement",
    "implementation",
    "including",
    "issue",
    "latest",
    "maintainer",
    "match",
    "maximum",
    "needed",
    "optional",
    "outcome",
    "phase",
    "planner",
    "planning",
    "prompt",
    "prompts",
    "refactor",
    "references",
    "remove",
    "required",
    "result",
    "revision",
    "small",
    "specific",
    "stale",
    "status",
    "suite",
    "tests",
    "through",
    "treat",
    "update",
    "verifier",
    "workflow",
}


@dataclass(frozen=True)
class SearchHit:
    path: str
    line: int | None
    detail: str

    def to_evidence(self) -> RepoFactEvidenceArtifact:
        return RepoFactEvidenceArtifact(path=self.path, line=self.line, detail=self.detail)


@dataclass(frozen=True)
class SearchableFile:
    path: str
    lines: tuple[str, ...]
    lower_lines: tuple[str, ...]


def build_repo_facts(epic_dir: Path, project_root: Path = PROJECT_ROOT) -> Path:
    """Build and write repo_facts.json for an epic directory."""
    epic = EpicArtifact.from_epic_dir(epic_dir)
    artifact = generate_repo_facts(epic, project_root=project_root)
    return artifact.write(epic_dir)


def generate_repo_facts(
    epic: EpicArtifact,
    *,
    project_root: Path = PROJECT_ROOT,
) -> RepoFactsArtifact:
    """Generate compact repo facts from epic text plus live repo inspection."""
    search_files = _build_search_index(project_root)
    optional_hints = load_optional_codebase_hints(project_root / ".planning" / "codebase")
    path_terms, route_terms, command_terms, keyword_terms = _extract_terms(epic.body, optional_hints)

    entry_points = _build_entry_point_facts(command_terms, route_terms, search_files)
    surfaces, exact_path_hits = _build_surface_facts(path_terms, keyword_terms, project_root, search_files)
    overlaps = _build_overlap_facts(keyword_terms, search_files)
    contradictions = _build_contradiction_facts(path_terms, route_terms, project_root, search_files)
    edit_targets = _build_edit_target_facts(exact_path_hits, surfaces, entry_points, overlaps)

    return RepoFactsArtifact(
        epic_number=epic.epic_number,
        current_entry_points=tuple(entry_points),
        relevant_existing_surfaces=tuple(surfaces),
        overlapping_implementations=tuple(overlaps),
        contradicted_assumptions=tuple(contradictions),
        likely_edit_targets=tuple(edit_targets),
    )


def _build_search_index(project_root: Path) -> list[SearchableFile]:
    files: list[SearchableFile] = []
    for path in sorted(project_root.rglob("*")):
        if path.is_dir():
            continue
        if _should_skip_search_path(path):
            continue
        if path.suffix not in SEARCHABLE_SUFFIXES and path.name not in SEARCHABLE_FILENAMES:
            continue
        try:
            lines = tuple(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(project_root).as_posix()
        files.append(
            SearchableFile(
                path=rel,
                lines=lines,
                lower_lines=tuple(line.lower() for line in lines),
            )
        )
    return files


def _should_skip_search_path(path: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    if any(part in SKIP_TOP_LEVEL_DIR_NAMES for part in path.parts):
        return True
    if ".planning" not in path.parts:
        return False

    planning_index = path.parts.index(".planning")
    planning_tail = path.parts[planning_index + 1 :]
    return not planning_tail or planning_tail[0] != "codebase"


def _extract_terms(
    epic_body: str,
    optional_hints: dict[str, list[str]],
) -> tuple[list[str], list[str], list[str], list[str]]:
    code_spans = [match.strip() for match in re.findall(r"`([^`\n]+)`", epic_body) if match.strip()]
    keyword_candidates = [*code_spans, *re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{4,}\b", epic_body)]
    keyword_terms = _unique_sorted(
        keyword_candidates,
        predicate=lambda value: _is_keyword_candidate(value),
    )[:16]
    command_terms = _unique_sorted(
        code_spans,
        predicate=lambda value: value.startswith("just ") or value.startswith("./wf "),
    )
    hint_paths = [
        hint
        for hint in optional_hints.get("paths", [])
        if any(token.lower() in hint.lower() for token in keyword_terms)
    ]
    path_terms = _unique_sorted(
        [
            *code_spans,
            *hint_paths,
            *re.findall(r"(?<![/\w])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", epic_body),
        ],
        predicate=lambda value: "/" in value and not value.startswith("http"),
    )
    route_terms = _unique_sorted(
        [
            *[
                endpoint.split(" ", 1)[1]
                for endpoint in optional_hints.get("endpoints", [])
                if " " in endpoint and any(token.lower() in endpoint.lower() for token in keyword_terms)
            ],
            *re.findall(r"(?<![A-Za-z0-9])/(?:[A-Za-z0-9_.-]+/?)+", epic_body),
        ],
        predicate=lambda value: " " not in value,
    )
    return path_terms[:12], route_terms[:8], command_terms[:6], keyword_terms


def _is_keyword_candidate(value: str) -> bool:
    token = value.strip().strip(".,:;()[]{}").lower()
    if not token or "/" in token or token in STOPWORDS:
        return False
    if len(token) < 5:
        return False
    if "_" in token or "." in token:
        return True
    return any(ch.isupper() for ch in value[1:]) or any(ch.isdigit() for ch in value)


def _unique_sorted(values: list[str], predicate) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or not predicate(normalized):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return sorted(result, key=str.lower)


def _search_hits(
    search_files: list[SearchableFile],
    term: str,
    *,
    max_hits: int = 4,
) -> list[SearchHit]:
    needle = term.lower()
    hits: list[SearchHit] = []
    for search_file in search_files:
        for index, lower_line in enumerate(search_file.lower_lines, start=1):
            if needle not in lower_line:
                continue
            hits.append(
                SearchHit(
                    path=search_file.path,
                    line=index,
                    detail=search_file.lines[index - 1].strip(),
                )
            )
            if len(hits) >= max_hits:
                return hits
    return hits


def _build_entry_point_facts(
    command_terms: list[str],
    route_terms: list[str],
    search_files: list[SearchableFile],
) -> list[RepoFactArtifact]:
    facts: list[RepoFactArtifact] = []
    for command in command_terms:
        hits = _search_hits(search_files, command, max_hits=2)
        if hits:
            facts.append(
                _fact(
                    f"Workflow entry point `{command}` is already surfaced in the repo.",
                    hits,
                )
            )
    for route in route_terms:
        hits = _search_hits(search_files, route, max_hits=3)
        if hits:
            facts.append(
                _fact(
                    f"Route or path `{route}` already appears in live repo surfaces.",
                    hits,
                )
            )
    return _dedupe_facts(facts)[:5]


def _build_surface_facts(
    path_terms: list[str],
    keyword_terms: list[str],
    project_root: Path,
    search_files: list[SearchableFile],
) -> tuple[list[RepoFactArtifact], dict[str, SearchHit]]:
    facts: list[RepoFactArtifact] = []
    exact_path_hits: dict[str, SearchHit] = {}

    for raw_path in path_terms:
        candidate = raw_path.lstrip("./")
        resolved = project_root / candidate
        if resolved.is_file():
            hit = SearchHit(path=resolved.relative_to(project_root).as_posix(), line=1, detail="File exists")
            exact_path_hits[hit.path] = hit
            facts.append(_fact(f"`{candidate}` already exists as a live repo surface.", [hit]))

    for keyword in keyword_terms:
        hits = _search_hits(search_files, keyword, max_hits=3)
        if not hits:
            continue
        facts.append(_fact(f"`{keyword}` already has live repo surfaces that overlap this epic.", hits))

    return _dedupe_facts(facts)[:6], exact_path_hits


def _build_overlap_facts(
    keyword_terms: list[str],
    search_files: list[SearchableFile],
) -> list[RepoFactArtifact]:
    facts: list[RepoFactArtifact] = []
    for keyword in keyword_terms:
        hits = _search_hits(search_files, keyword, max_hits=6)
        top_level_dirs = {hit.path.split("/", 1)[0] for hit in hits}
        if len(top_level_dirs) < 2:
            continue
        facts.append(
            _fact(
                f"`{keyword}` already spans multiple live repo surfaces and may require coordinated edits.",
                hits[:3],
            )
        )
    return _dedupe_facts(facts)[:4]


def _build_contradiction_facts(
    path_terms: list[str],
    route_terms: list[str],
    project_root: Path,
    search_files: list[SearchableFile],
) -> list[RepoFactArtifact]:
    facts: list[RepoFactArtifact] = []

    for raw_path in path_terms:
        candidate = raw_path.lstrip("./")
        if (project_root / candidate).exists():
            continue
        basename = Path(candidate).name
        alt_hits = [
            SearchHit(path=search_file.path, line=1, detail="Nearby path exists")
            for search_file in search_files
            if Path(search_file.path).name == basename
        ][:3]
        if alt_hits:
            facts.append(
                _fact(
                    f"Epic cites `{candidate}`, but the live repo currently places that surface elsewhere.",
                    alt_hits,
                )
            )

    for route in route_terms:
        if _search_hits(search_files, route, max_hits=1):
            continue
        segment = route.rstrip("/").split("/")[-1]
        if len(segment) < 3:
            continue
        alt_hits = _search_hits(search_files, segment, max_hits=3)
        if alt_hits:
            facts.append(
                _fact(
                    f"Epic cites route `{route}`, but only related live repo surfaces for `{segment}` were found.",
                    alt_hits,
                )
            )

    return _dedupe_facts(facts)[:4]


def _build_edit_target_facts(
    exact_path_hits: dict[str, SearchHit],
    surfaces: list[RepoFactArtifact],
    entry_points: list[RepoFactArtifact],
    overlaps: list[RepoFactArtifact],
) -> list[RepoFactArtifact]:
    ranked: dict[str, SearchHit] = {}
    for hit in exact_path_hits.values():
        ranked.setdefault(hit.path, hit)
    for fact in [*surfaces, *entry_points, *overlaps]:
        for evidence in fact.evidence:
            if evidence.path.endswith((".py", ".md", ".json", ".toml")):
                ranked.setdefault(
                    evidence.path,
                    SearchHit(
                        path=evidence.path,
                        line=evidence.line,
                        detail=evidence.detail,
                    ),
                )

    facts = [
        _fact(f"`{path}` is a likely edit target for this epic.", [hit])
        for path, hit in sorted(ranked.items())
    ]
    return facts[:6]


def _fact(statement: str, hits: list[SearchHit]) -> RepoFactArtifact:
    evidence = tuple(hit.to_evidence() for hit in hits[:3])
    return RepoFactArtifact(statement=statement, evidence=evidence)


def _dedupe_facts(facts: list[RepoFactArtifact]) -> list[RepoFactArtifact]:
    seen: set[str] = set()
    deduped: list[RepoFactArtifact] = []
    for fact in facts:
        key = fact.statement
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped
