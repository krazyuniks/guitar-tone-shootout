#!/usr/bin/env python3
"""
Static analysis for test quality.

Usage:
    python scripts/test_quality_check.py src/ tests/
    python scripts/test_quality_check.py --strict tests/
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Patterns that indicate low-quality tests
ANTIPATTERNS = [
    # Trivial assertions
    (
        r"expect\(true\)\.toBe\(true\)",
        "trivial_assertion",
        "error",
        "Trivial assertion: expect(true).toBe(true)",
    ),
    (
        r"expect\(false\)\.toBe\(false\)",
        "trivial_assertion",
        "error",
        "Trivial assertion: expect(false).toBe(false)",
    ),
    (
        r"assert\s+True\s*$",
        "trivial_assertion",
        "error",
        "Trivial assertion: assert True",
    ),
    (
        r"assertEquals?\(true,\s*true\)",
        "trivial_assertion",
        "error",
        "Trivial assertion: assertEquals(true, true)",
    ),
    # Weak assertions
    (
        r"expect\(\w+\)\.toBeTruthy\(\)",
        "weak_assertion",
        "warning",
        "Weak assertion: prefer explicit value check over toBeTruthy()",
    ),
    (
        r"expect\(\w+\)\.toBeDefined\(\)",
        "weak_assertion",
        "warning",
        "Weak assertion: toBeDefined() doesn't verify correctness",
    ),
    (
        r"assert\s+\w+\s*$",
        "weak_assertion",
        "warning",
        "Weak assertion: truthy check without explicit comparison",
    ),
    # Spy-only tests
    (
        r"expect\(\w+\)\.toHaveBeenCalled\(\)\s*;?\s*\n\s*\}",
        "spy_only",
        "warning",
        "Test only verifies call happened, not the effect",
    ),
    (
        r"\.toHaveBeenCalledWith\([^)]+\)\s*;?\s*\n\s*\}",
        "spy_only",
        "warning",
        "Test only verifies arguments, not the result",
    ),
    # Empty tests
    (
        r"it\(['\"][^'\"]+['\"]\s*,\s*\(\)\s*=>\s*\{\s*\}\)",
        "empty_test",
        "error",
        "Empty test body",
    ),
    (
        r"test\(['\"][^'\"]+['\"]\s*,\s*\(\)\s*=>\s*\{\s*\}\)",
        "empty_test",
        "error",
        "Empty test body",
    ),
    # Commented assertions
    (
        r"//\s*expect\(",
        "commented_assertion",
        "warning",
        "Commented out assertion",
    ),
    (
        r"//\s*assert",
        "commented_assertion",
        "warning",
        "Commented out assertion",
    ),
    # Snapshot overuse
    (
        r"\.toMatchSnapshot\(\)",
        "snapshot_overuse",
        "warning",
        "Snapshot tests don't verify behaviour, only detect changes",
    ),
    # Excessive mocking
    (
        r"jest\.mock\(['\"]\.\.?/",
        "mock_implementation",
        "warning",
        "Mocking relative import - verify you're not mocking the subject under test",
    ),
    # Skip/only
    (
        r"\.skip\(",
        "skipped_test",
        "warning",
        "Skipped test - should be fixed or removed",
    ),
    (
        r"\.only\(",
        "focused_test",
        "error",
        "Focused test (.only) - will skip other tests",
    ),
]


@dataclass
class Issue:
    file: str
    line: int
    type: str
    severity: str
    message: str


def check_file(path: Path) -> list[Issue]:
    issues = []

    try:
        content = path.read_text()
    except Exception as e:
        return [Issue(str(path), 0, "read_error", "error", str(e))]

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        for pattern, issue_type, severity, message in ANTIPATTERNS:
            if re.search(pattern, line):
                issues.append(
                    Issue(
                        file=str(path),
                        line=i,
                        type=issue_type,
                        severity=severity,
                        message=message,
                    )
                )

    # Check for tests without assertions
    test_blocks = re.finditer(
        r"(it|test)\(['\"]([^'\"]+)['\"]\s*,\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([^}]+)\}",
        content,
        re.DOTALL,
    )

    for match in test_blocks:
        test_name = match.group(2)
        test_body = match.group(3)

        has_assertion = any(
            kw in test_body
            for kw in ["expect(", "assert", "should.", ".to.", "assertEquals"]
        )

        if not has_assertion:
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                Issue(
                    file=str(path),
                    line=line_num,
                    type="no_assertion",
                    severity="error",
                    message=f"Test '{test_name}' has no assertions",
                )
            )

    return issues


def check_paths(paths: list[Path], strict: bool = False) -> tuple[bool, list[Issue]]:
    all_issues = []
    test_patterns = ["*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx"]

    for path in paths:
        if path.is_dir():
            for pattern in test_patterns:
                for f in path.rglob(pattern):
                    if "node_modules" not in str(f):
                        all_issues.extend(check_file(f))
        elif path.exists():
            all_issues.extend(check_file(path))

    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]

    # In strict mode, warnings are errors
    if strict:
        errors.extend(warnings)
        warnings = []

    passed = len(errors) == 0
    return passed, all_issues


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test quality checker")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()

    passed, issues = check_paths(args.paths, args.strict)

    if args.format == "json":
        import json

        print(
            json.dumps(
                [
                    {
                        "file": i.file,
                        "line": i.line,
                        "type": i.type,
                        "severity": i.severity,
                        "message": i.message,
                    }
                    for i in issues
                ],
                indent=2,
            )
        )
    else:
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        for issue in issues:
            icon = "✗" if issue.severity == "error" else "⚠"
            print(f"{icon} {issue.file}:{issue.line} [{issue.type}]")
            print(f"  {issue.message}")

        print()
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}")

        if passed:
            print("✓ Test quality check passed")
        else:
            print("✗ Test quality check failed")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
