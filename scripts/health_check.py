#!/usr/bin/env python3
"""
Health checks to verify system actually works.

Usage:
    python scripts/health_check.py E42
"""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HealthResult:
    check: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


class HealthChecker:
    def __init__(self, epic_id: str):
        self.epic_id = epic_id
        self.results: list[HealthResult] = []

    def run_all(self) -> bool:
        self.check_build()
        self.check_typecheck()
        self.check_tests()
        self.check_e2e()
        return all(r.passed for r in self.results)

    def _run(self, cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def check_build(self):
        result = self._run(["just", "build"])
        self.results.append(HealthResult(
            check="build",
            passed=result.returncode == 0,
            message="Build succeeded" if result.returncode == 0 else "Build failed",
            details={"stderr": result.stderr[-1000:]} if result.returncode != 0 else {}
        ))

    def check_typecheck(self):
        result = self._run(["just", "typecheck"])
        self.results.append(HealthResult(
            check="typecheck",
            passed=result.returncode == 0,
            message="Types OK" if result.returncode == 0 else "Type errors",
            details={"output": result.stdout[-1000:]} if result.returncode != 0 else {}
        ))

    def check_tests(self):
        result = self._run(["just", "test"])
        self.results.append(HealthResult(
            check="tests",
            passed=result.returncode == 0,
            message="Tests passed" if result.returncode == 0 else "Tests failed",
            details={"output": result.stderr[-1000:]} if result.returncode != 0 else {}
        ))

    def check_e2e(self):
        result = self._run(["just", "e2e"])
        self.results.append(HealthResult(
            check="e2e",
            passed=result.returncode == 0,
            message="E2E passed" if result.returncode == 0 else "E2E failed",
            details={"output": result.stderr[-1000:]} if result.returncode != 0 else {}
        ))

    def report(self) -> str:
        lines = [f"# Health Check: {self.epic_id}\n"]
        all_passed = all(r.passed for r in self.results)
        lines.append(f"**Status**: {'✅ HEALTHY' if all_passed else '❌ UNHEALTHY'}\n")
        lines.append("| Check | Status | Message |")
        lines.append("|-------|--------|---------|")
        for r in self.results:
            icon = "✅" if r.passed else "❌"
            lines.append(f"| {r.check} | {icon} | {r.message} |")
        return "\n".join(lines)

    def save_report(self):
        report = self.report()
        # Find epic directory
        for epic_dir in Path(".tasks").rglob(f"E{self.epic_id.replace('E', '')}"):
            if epic_dir.is_dir():
                report_path = epic_dir / "health-report.md"
                report_path.write_text(report)
                print(f"Report saved to {report_path}")
                return
        # Fallback
        print(report)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("epic_id", help="Epic ID (e.g., E42 or 42)")
    args = parser.parse_args()

    checker = HealthChecker(args.epic_id)
    passed = checker.run_all()
    checker.save_report()
    print(checker.report())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
