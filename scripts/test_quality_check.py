#!/usr/bin/env python3
"""
Static analysis for test quality (Python/pytest).

Usage:
    python scripts/test_quality_check.py tests/
    python scripts/test_quality_check.py --strict tests/unit/
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Patterns that indicate low-quality tests (Python/pytest)
ANTIPATTERNS = [
    # Trivial assertions
    (
        r"assert\s+True\s*$",
        "trivial_assertion",
        "error",
        "Trivial assertion: assert True",
    ),
    (
        r"assert\s+False\s*$",
        "trivial_assertion",
        "error",
        "Trivial assertion: assert False (always fails)",
    ),
    (
        r"assert\s+1\s*==\s*1",
        "trivial_assertion",
        "error",
        "Trivial assertion: assert 1 == 1",
    ),
    (
        r'assert\s+["\'][^"\']+["\']\s*==\s*["\'][^"\']+["\']',
        "trivial_assertion",
        "warning",
        "Assertion compares string literals - verify this is intentional",
    ),
    # Weak assertions (truthy checks without explicit comparison)
    (
        r"assert\s+\w+\s*$",
        "weak_assertion",
        "warning",
        "Weak assertion: truthy check without explicit comparison",
    ),
    (
        r"assert\s+\w+\s+is\s+not\s+None\s*$",
        "weak_assertion",
        "warning",
        "Weak assertion: 'is not None' doesn't verify correctness",
    ),
    # Mock-only tests (testing mocks, not behaviour)
    (
        r"mock\.\w+\.assert_called\(\)\s*$",
        "mock_only",
        "warning",
        "Test only verifies mock was called, not the effect",
    ),
    (
        r"\.assert_called_once\(\)\s*$",
        "mock_only",
        "warning",
        "Test only verifies call count, not the result",
    ),
    # Commented assertions
    (
        r"#\s*assert\s+",
        "commented_assertion",
        "warning",
        "Commented out assertion",
    ),
    # Skip markers
    (
        r"@pytest\.mark\.skip",
        "skipped_test",
        "warning",
        "Skipped test - should be fixed or removed",
    ),
    (
        r"pytest\.skip\(",
        "skipped_test",
        "warning",
        "Programmatically skipped test",
    ),
    # xfail without reason
    (
        r"@pytest\.mark\.xfail\s*$",
        "xfail_no_reason",
        "warning",
        "xfail without reason - add reason='...'",
    ),
    # Empty test functions
    (
        r"def\s+test_\w+\([^)]*\):\s*\n\s*pass\s*$",
        "empty_test",
        "error",
        "Empty test body (pass only)",
    ),
    (
        r'def\s+test_\w+\([^)]*\):\s*\n\s*"""[^"]*"""\s*\n\s*pass\s*$',
        "empty_test",
        "error",
        "Empty test body (docstring + pass only)",
    ),
    # TODO in test
    (
        r"#\s*TODO.*assert",
        "todo_assertion",
        "warning",
        "TODO comment about assertion - test may be incomplete",
    ),
    # Broad exception catching in tests
    (
        r"except\s+Exception\s*:",
        "broad_except",
        "warning",
        "Broad exception catch - use specific exception type",
    ),
    # Sleep in tests (flaky indicator)
    (
        r"time\.sleep\(",
        "sleep_in_test",
        "warning",
        "Sleep in test - may cause flakiness, consider mocking time",
    ),
    (
        r"asyncio\.sleep\(",
        "sleep_in_test",
        "warning",
        "Async sleep in test - may cause flakiness",
    ),
    # =========================================================================
    # Mock violations — ERRORS (block the lock)
    # =========================================================================
    (
        r"from unittest\.mock import",
        "mock_import",
        "error",
        "BANNED: unittest.mock import — use real services",
    ),
    (
        r"from unittest import mock",
        "mock_import",
        "error",
        "BANNED: unittest.mock import — use real services",
    ),
    (
        r"@patch\(",
        "mock_patch",
        "error",
        "BANNED: @patch decorator — use real services",
    ),
    (
        r"@patch\.object\(",
        "mock_patch",
        "error",
        "BANNED: @patch.object decorator — use real services",
    ),
    (
        r"\bMock\(",
        "mock_usage",
        "error",
        "BANNED: Mock() — use real services",
    ),
    (
        r"\bMagicMock\(",
        "mock_usage",
        "error",
        "BANNED: MagicMock() — use real services",
    ),
    (
        r"\bAsyncMock\(",
        "mock_usage",
        "error",
        "BANNED: AsyncMock() — use real services",
    ),
    (
        r"\.return_value\s*=",
        "mock_config",
        "error",
        "BANNED: mock .return_value — use real services",
    ),
    (
        r"\.side_effect\s*=",
        "mock_config",
        "error",
        "BANNED: mock .side_effect — use real services",
    ),
    # =========================================================================
    # SQLite violations — ERRORS (block the lock)
    # =========================================================================
    (
        r"sqlite",
        "sqlite_usage",
        "error",
        "BANNED: SQLite — use real PostgreSQL",
    ),
    (
        r"aiosqlite",
        "sqlite_usage",
        "error",
        "BANNED: aiosqlite — use real PostgreSQL",
    ),
    (
        r"PRAGMA",
        "sqlite_usage",
        "error",
        "BANNED: SQLite PRAGMA — use real PostgreSQL",
    ),
    (
        r"xfail.*[Pp]re.existing",
        "xfail_preexisting",
        "error",
        "BANNED: xfail with 'pre-existing' reason — fix the test",
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
    """Check a single test file for quality issues."""
    issues = []

    try:
        content = path.read_text()
    except Exception as e:
        return [Issue(str(path), 0, "read_error", "error", str(e))]

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        for pattern, issue_type, severity, message in ANTIPATTERNS:
            if re.search(pattern, line, re.MULTILINE):
                issues.append(
                    Issue(
                        file=str(path),
                        line=i,
                        type=issue_type,
                        severity=severity,
                        message=message,
                    )
                )

    # Check for test functions without assertions
    test_func_pattern = re.compile(
        r"(async\s+)?def\s+(test_\w+)\([^)]*\):\s*\n((?:(?!\ndef\s).)*)",
        re.DOTALL,
    )

    for match in test_func_pattern.finditer(content):
        test_name = match.group(2)
        test_body = match.group(3)

        # Check if body has an assertion
        has_assertion = any(
            kw in test_body
            for kw in [
                "assert ",
                "pytest.raises",
                "pytest.warns",
                "pytest.approx",
                ".assert_",  # mock assertions
                "self.assert",  # unittest style
            ]
        )

        # Skip if it's a fixture or helper
        if "yield" in test_body or "return" in test_body:
            continue

        # Skip if it just calls another function that likely has assertions
        if test_body.strip().startswith("await ") or test_body.strip().startswith("return "):
            continue

        if not has_assertion and "pass" not in test_body:
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                Issue(
                    file=str(path),
                    line=line_num,
                    type="no_assertion",
                    severity="warning",
                    message=f"Test '{test_name}' may have no assertions",
                )
            )

    return issues


def check_paths(paths: list[Path], strict: bool = False) -> tuple[bool, list[Issue]]:
    """Check all test files in the given paths."""
    all_issues = []
    test_patterns = ["test_*.py", "*_test.py"]

    for path in paths:
        if path.is_dir():
            for pattern in test_patterns:
                for f in path.rglob(pattern):
                    if "__pycache__" not in str(f) and ".venv" not in str(f):
                        all_issues.extend(check_file(f))
        elif path.exists() and path.name.startswith("test_"):
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

    parser = argparse.ArgumentParser(description="Test quality checker (Python/pytest)")
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
            icon = "x" if issue.severity == "error" else "!"
            print(f"{icon} {issue.file}:{issue.line} [{issue.type}]")
            print(f"  {issue.message}")

        print()
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}")

        if passed:
            print("Test quality check passed")
        else:
            print("Test quality check failed")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
