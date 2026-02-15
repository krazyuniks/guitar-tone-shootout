#!/usr/bin/env python3
"""Deterministic codebase mapper for GTS project.

Generates structured markdown files describing the codebase:
  - STRUCTURE.md  -- Directory tree with file counts
  - SCHEMA.md     -- ORM model summary (tables, columns, relationships)
  - ENDPOINTS.md  -- FastAPI endpoint inventory
  - IMPORTS.md    -- Internal import graph
  - TESTS.md      -- Test inventory grouped by category

Uses only Python stdlib (ast, os, pathlib, re). No external dependencies.

Usage:
    python workflow/codebase_mapper.py
    python workflow/codebase_mapper.py --project-root /path/to/gts
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

# Directories to exclude from the tree walk
EXCLUDED_DIRS: set[str] = {
    "__pycache__",
    ".git",
    "node_modules",
    "dist",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pypackages__",
    ".eggs",
}

# Patterns for egg-info dirs
EXCLUDED_DIR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r".*\.egg-info$"),
]

# Internal packages for import graph filtering
INTERNAL_PACKAGES: set[str] = {
    "core",
    "audio",
    "video",
    "webapp",
    "worker",
    "scheduler",
    "source_t3k",
}

# Source directories for import graph extraction
IMPORT_SOURCE_DIRS: list[str] = [
    "libs",
    "apps",
    "sources",
]

# ORM model directory (relative to project root)
ORM_MODELS_DIR = "apps/webapp/src/webapp/adapters/persistence/models"

# API route directories (relative to project root)
API_DIRS: list[str] = [
    "apps/webapp/src/webapp/api",
]

# Test root directory (relative to project root)
TESTS_DIR = "tests"


def _is_excluded_dir(dirname: str) -> bool:
    """Check whether a directory name should be excluded."""
    if dirname in EXCLUDED_DIRS:
        return True
    return any(p.match(dirname) for p in EXCLUDED_DIR_PATTERNS)


# ---------------------------------------------------------------------------
# 1. Directory tree
# ---------------------------------------------------------------------------


def _build_directory_tree(root: Path) -> str:
    """Build an indented directory tree with file counts per directory.

    Excludes directories matching EXCLUDED_DIRS and EXCLUDED_DIR_PATTERNS.
    Returns a multi-line string suitable for embedding in markdown.
    """
    lines: list[str] = []
    root_str = str(root)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Filter out excluded directories (modifying dirnames in place)
        dirnames[:] = sorted(d for d in dirnames if not _is_excluded_dir(d))
        filenames = sorted(filenames)

        rel = os.path.relpath(dirpath, root_str)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * depth
        dirname = os.path.basename(dirpath) if rel != "." else root.name

        file_count = len(filenames)
        count_label = f"  ({file_count} files)" if file_count > 0 else ""

        lines.append(f"{indent}{dirname}/{count_label}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Import graph
# ---------------------------------------------------------------------------


def _extract_imports_from_file(filepath: Path) -> set[str]:
    """Parse a Python file and return the set of top-level imported module names."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imports.add(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            imports.add(top)
    return imports


def _module_name_from_path(filepath: Path, project_root: Path) -> str | None:
    """Derive an internal module name from a file path.

    Returns the first matching internal package name, or None if the file
    does not belong to a known internal package.
    """
    rel = filepath.relative_to(project_root)
    parts = rel.parts

    # Walk the path parts looking for a 'src' directory followed by the package
    for i, part in enumerate(parts):
        if part == "src" and i + 1 < len(parts):
            pkg = parts[i + 1]
            if pkg in INTERNAL_PACKAGES:
                return pkg

    return None


def _build_import_graph(project_root: Path) -> dict[str, set[str]]:
    """Build module -> internal dependencies mapping.

    Scans all .py files under IMPORT_SOURCE_DIRS and extracts imports
    that reference INTERNAL_PACKAGES. Results are aggregated per package.
    """
    graph: dict[str, set[str]] = {}

    for src_dir_name in IMPORT_SOURCE_DIRS:
        src_dir = project_root / src_dir_name
        if not src_dir.is_dir():
            continue

        for py_file in sorted(src_dir.rglob("*.py")):
            # Skip excluded dirs
            if any(_is_excluded_dir(p) for p in py_file.relative_to(project_root).parts):
                continue

            module = _module_name_from_path(py_file, project_root)
            if module is None:
                continue

            raw_imports = _extract_imports_from_file(py_file)
            internal_deps = {imp for imp in raw_imports if imp in INTERNAL_PACKAGES}
            # Remove self-dependency
            internal_deps.discard(module)

            if module not in graph:
                graph[module] = set()
            graph[module].update(internal_deps)

    return graph


def _format_import_graph(graph: dict[str, set[str]]) -> str:
    """Format import graph as markdown."""
    lines: list[str] = []
    for module in sorted(graph):
        deps = sorted(graph[module])
        if deps:
            lines.append(f"- **{module}** -> {', '.join(deps)}")
        else:
            lines.append(f"- **{module}** -> (none)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. ORM schema
# ---------------------------------------------------------------------------


def _extract_orm_schema(project_root: Path) -> list[dict]:
    """Parse SQLAlchemy model files and extract schema information.

    Returns a list of dicts, each with:
      - class_name: str
      - tablename: str
      - columns: list of (name, type_str)
      - relationships: list of (name, target, back_populates, lazy)
    """
    models_dir = project_root / ORM_MODELS_DIR
    if not models_dir.is_dir():
        return []

    results: list[dict] = []

    for py_file in sorted(models_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if it inherits from Base (directly or via mixin)
            tablename = None
            columns: list[tuple[str, str]] = []
            relationships: list[tuple[str, str, str, str]] = []

            for item in node.body:
                # Extract __tablename__
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__tablename__"
                            and isinstance(item.value, ast.Constant)
                        ):
                            tablename = item.value.value

                # Extract Mapped[] columns and relationship()
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    col_name = item.target.id
                    # Skip dunder attrs
                    if col_name.startswith("__"):
                        continue

                    # Try to get the type annotation as a string
                    type_str = _annotation_to_str(item.annotation)

                    # Check if value is a relationship() call
                    if item.value and _is_call_to(item.value, "relationship"):
                        rel_info = _parse_relationship(item.value)
                        relationships.append(
                            (
                                col_name,
                                rel_info.get("target", "?"),
                                rel_info.get("back_populates", ""),
                                rel_info.get("lazy", ""),
                            )
                        )
                    elif item.value and _is_call_to(item.value, "synonym"):
                        # Skip synonyms
                        continue
                    else:
                        columns.append((col_name, type_str))

            if tablename is not None:
                results.append(
                    {
                        "class_name": node.name,
                        "tablename": tablename,
                        "columns": columns,
                        "relationships": relationships,
                        "file": py_file.name,
                    }
                )

    return results


def _annotation_to_str(node: ast.expr) -> str:
    """Convert an AST annotation node to a readable string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return f"{_annotation_to_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        base = _annotation_to_str(node.value)
        sl = _annotation_to_str(node.slice)
        return f"{base}[{sl}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _annotation_to_str(node.left)
        right = _annotation_to_str(node.right)
        return f"{left} | {right}"
    if isinstance(node, ast.Tuple):
        elts = ", ".join(_annotation_to_str(e) for e in node.elts)
        return elts
    return "..."


def _is_call_to(node: ast.expr, func_name: str) -> bool:
    """Check if an AST node is a call to a specific function name."""
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == func_name
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == func_name
    return False


def _parse_relationship(call: ast.Call) -> dict[str, str]:
    """Extract target, back_populates, lazy from a relationship() call."""
    info: dict[str, str] = {}

    # First positional arg is target class name
    if call.args and isinstance(call.args[0], ast.Constant):
        info["target"] = str(call.args[0].value)

    for kw in call.keywords:
        if kw.arg == "back_populates" and isinstance(kw.value, ast.Constant):
            info["back_populates"] = str(kw.value.value)
        elif kw.arg == "lazy" and isinstance(kw.value, ast.Constant):
            info["lazy"] = str(kw.value.value)

    return info


def _format_orm_schema(models: list[dict]) -> str:
    """Format ORM schema information as markdown."""
    lines: list[str] = []

    for model in models:
        lines.append(f"### {model['class_name']} (`{model['tablename']}`)")
        lines.append(f"*File: {model['file']}*")
        lines.append("")

        if model["columns"]:
            lines.append("**Columns:**")
            lines.append("")
            lines.append("| Column | Type |")
            lines.append("|--------|------|")
            for col_name, col_type in model["columns"]:
                lines.append(f"| `{col_name}` | `{col_type}` |")
            lines.append("")

        if model["relationships"]:
            lines.append("**Relationships:**")
            lines.append("")
            lines.append("| Name | Target | back_populates | lazy |")
            lines.append("|------|--------|----------------|------|")
            for name, target, bp, lazy in model["relationships"]:
                lines.append(f"| `{name}` | {target} | {bp} | {lazy} |")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. API endpoints
# ---------------------------------------------------------------------------


def _extract_endpoints(project_root: Path) -> list[dict]:
    """Parse FastAPI route files and extract endpoint information.

    Returns a list of dicts with:
      - method: str (GET, POST, PUT, DELETE, PATCH)
      - path: str
      - function_name: str
      - response_model: str | None
      - status_code: str | None
      - file: str (relative path)
    """
    results: list[dict] = []

    for api_dir_name in API_DIRS:
        api_dir = project_root / api_dir_name
        if not api_dir.is_dir():
            continue

        for py_file in sorted(api_dir.rglob("*.py")):
            if py_file.name.startswith("_"):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            # Find the router prefix
            router_prefix = _find_router_prefix(tree)

            rel_path = py_file.relative_to(project_root)

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue

                for decorator in node.decorator_list:
                    endpoint_info = _parse_route_decorator(decorator, router_prefix)
                    if endpoint_info:
                        endpoint_info["function_name"] = node.name
                        endpoint_info["file"] = str(rel_path)
                        results.append(endpoint_info)

    return results


def _find_router_prefix(tree: ast.Module) -> str:
    """Find the APIRouter prefix from module-level assignments."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "router"
                    and isinstance(node.value, ast.Call)
                ):
                    for kw in node.value.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            return str(kw.value.value)
    return ""


def _parse_route_decorator(decorator: ast.expr, router_prefix: str) -> dict | None:
    """Parse a @router.get/post/etc decorator and extract route info."""
    if not isinstance(decorator, ast.Call):
        return None

    # Check for router.get, router.post, etc.
    if not isinstance(decorator.func, ast.Attribute):
        return None

    method_map = {"get", "post", "put", "delete", "patch", "head", "options"}
    method_name = decorator.func.attr.lower()
    if method_name not in method_map:
        return None

    # Check that the object is 'router'
    if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id != "router":
        return None

    info: dict[str, str | None] = {
        "method": method_name.upper(),
        "path": router_prefix,
        "response_model": None,
        "status_code": None,
    }

    # First positional arg is the path suffix
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        suffix = str(decorator.args[0].value)
        info["path"] = router_prefix + suffix

    for kw in decorator.keywords:
        if kw.arg == "response_model":
            info["response_model"] = _annotation_to_str(kw.value)
        elif kw.arg == "status_code":
            info["status_code"] = _annotation_to_str(kw.value)

    return info


def _format_endpoints(endpoints: list[dict]) -> str:
    """Format endpoint information as markdown."""
    lines: list[str] = []

    # Group by file
    by_file: dict[str, list[dict]] = {}
    for ep in endpoints:
        f = ep["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(ep)

    for filepath in sorted(by_file):
        lines.append(f"### `{filepath}`")
        lines.append("")
        lines.append("| Method | Path | Function | Response Model | Status |")
        lines.append("|--------|------|----------|----------------|--------|")

        for ep in by_file[filepath]:
            method = ep["method"]
            path = ep["path"]
            func = ep["function_name"]
            resp = ep.get("response_model") or ""
            stat = ep.get("status_code") or ""
            lines.append(f"| {method} | `{path}` | `{func}` | {resp} | {stat} |")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Test inventory
# ---------------------------------------------------------------------------


def _extract_tests(project_root: Path) -> dict[str, list[dict]]:
    """Extract test functions from test files.

    Returns a dict mapping category (unit, integration, regression, e2e)
    to a list of dicts with:
      - file: str (relative path)
      - functions: list[str]
    """
    tests_dir = project_root / TESTS_DIR
    if not tests_dir.is_dir():
        return {}

    results: dict[str, list[dict]] = {}

    for py_file in sorted(tests_dir.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        if not py_file.name.startswith("test_") and not py_file.name.endswith("_test.py"):
            # Also include conftest for completeness? No, only test files.
            continue

        # Skip files in excluded dirs
        rel = py_file.relative_to(project_root)
        if any(_is_excluded_dir(p) for p in rel.parts):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        test_functions: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                test_functions.append(node.name)

        if not test_functions:
            continue

        # Determine category from path
        rel_to_tests = py_file.relative_to(tests_dir)
        parts = rel_to_tests.parts
        category = parts[0] if len(parts) >= 1 else "other"

        if category not in results:
            results[category] = []
        results[category].append(
            {
                "file": str(rel),
                "functions": sorted(test_functions),
            }
        )

    return results


def _format_test_inventory(inventory: dict[str, list[dict]]) -> str:
    """Format test inventory as markdown."""
    lines: list[str] = []

    total_tests = 0
    total_files = 0

    for category in sorted(inventory):
        entries = inventory[category]
        cat_tests = sum(len(e["functions"]) for e in entries)
        cat_files = len(entries)
        total_tests += cat_tests
        total_files += cat_files

        lines.append(f"### {category} ({cat_files} files, {cat_tests} tests)")
        lines.append("")

        for entry in entries:
            func_count = len(entry["functions"])
            lines.append(f"**`{entry['file']}`** ({func_count} tests)")
            for func in entry["functions"]:
                lines.append(f"- `{func}`")
            lines.append("")

    # Summary at the top (will be prepended)
    summary = f"**Total: {total_files} test files, {total_tests} test functions**\n"

    return summary + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def _write_structure(project_root: Path, output_dir: Path) -> Path:
    """Generate STRUCTURE.md."""
    tree = _build_directory_tree(project_root)
    content = (
        "# Codebase Structure\n"
        "\n"
        "*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*\n"
        "\n"
        "## Directory Tree\n"
        "\n"
        "```\n"
        f"{tree}\n"
        "```\n"
    )
    out = output_dir / "STRUCTURE.md"
    out.write_text(content, encoding="utf-8")
    return out


def _write_schema(project_root: Path, output_dir: Path) -> Path:
    """Generate SCHEMA.md."""
    models = _extract_orm_schema(project_root)
    formatted = _format_orm_schema(models)
    content = (
        "# ORM Schema\n"
        "\n"
        "*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*\n"
        "\n"
        f"**{len(models)} models extracted** from `{ORM_MODELS_DIR}/`\n"
        "\n"
        f"{formatted}"
    )
    out = output_dir / "SCHEMA.md"
    out.write_text(content, encoding="utf-8")
    return out


def _write_endpoints(project_root: Path, output_dir: Path) -> Path:
    """Generate ENDPOINTS.md."""
    endpoints = _extract_endpoints(project_root)
    formatted = _format_endpoints(endpoints)
    content = (
        "# API Endpoints\n"
        "\n"
        "*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*\n"
        "\n"
        f"**{len(endpoints)} endpoints extracted** from `{', '.join(API_DIRS)}`\n"
        "\n"
        f"{formatted}"
    )
    out = output_dir / "ENDPOINTS.md"
    out.write_text(content, encoding="utf-8")
    return out


def _write_imports(project_root: Path, output_dir: Path) -> Path:
    """Generate IMPORTS.md."""
    graph = _build_import_graph(project_root)
    formatted = _format_import_graph(graph)
    content = (
        "# Internal Import Graph\n"
        "\n"
        "*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*\n"
        "\n"
        f"**{len(graph)} internal packages** scanned from "
        f"`{', '.join(IMPORT_SOURCE_DIRS)}`\n"
        "\n"
        "Internal packages: "
        f"{', '.join(sorted(INTERNAL_PACKAGES))}\n"
        "\n"
        "## Dependencies\n"
        "\n"
        f"{formatted}\n"
    )
    out = output_dir / "IMPORTS.md"
    out.write_text(content, encoding="utf-8")
    return out


def _write_tests(project_root: Path, output_dir: Path) -> Path:
    """Generate TESTS.md."""
    inventory = _extract_tests(project_root)
    formatted = _format_test_inventory(inventory)
    content = (
        "# Test Inventory\n"
        "\n"
        "*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*\n"
        "\n"
        f"{formatted}"
    )
    out = output_dir / "TESTS.md"
    out.write_text(content, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="GTS deterministic codebase mapper")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current working directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <project-root>/.planning/codebase)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    output_dir = (args.output_dir or project_root / ".planning" / "codebase").resolve()

    if not project_root.is_dir():
        print(f"Error: project root does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Project root: {project_root}")
    print(f"Output dir:   {output_dir}")
    print()

    files = [
        ("STRUCTURE.md", _write_structure),
        ("SCHEMA.md", _write_schema),
        ("ENDPOINTS.md", _write_endpoints),
        ("IMPORTS.md", _write_imports),
        ("TESTS.md", _write_tests),
    ]

    total_chars = 0
    for label, writer in files:
        path = writer(project_root, output_dir)
        size = path.stat().st_size
        total_chars += size
        print(f"  {label:20s} {size:>8,d} bytes")

    # Rough token estimate: ~4 chars per token for English/code
    est_tokens = total_chars // 4

    print()
    print(f"Total: {total_chars:,d} characters (~{est_tokens:,d} tokens)")


if __name__ == "__main__":
    main()
