"""Structural guard: only the transition service writes Job.status/Shootout.status.

docs/design/job-system-contract.md makes webapp.services.job_transitions the
sole writer of both status fields (with webapp.services.job_dispatch owning
exactly the PENDING -> QUEUED outbox edge). Everything else in the allowlist
below is a legacy writer awaiting migration by its named backlog unit; this
test is a ratchet - adding a NEW direct status write anywhere fails it, and
migrating a legacy writer requires shrinking the list, never growing it.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

REPO = Path("/app")

# ORM assignments to a .status attribute: enum literals plus the transition
# service's dynamic target write (job.status = to_status).
ORM_WRITE = re.compile(r"\.status\s*=\s*(?:(?:JobStatus|ShootoutStatus)\.|to_status\b)")
# Raw-SQL writes that bypass the ORM entirely.
RAW_WRITE = re.compile(r"UPDATE\s+(?:core_jobs|core_shootouts)\s+SET\s+status", re.IGNORECASE)

# file (repo-relative) -> exact number of status writes sanctioned there.
ALLOWED: dict[str, int] = {
    # The transition service itself: transition_job + reconcile_parent projection.
    "apps/webapp/src/webapp/services/job_transitions.py": 5,
    # The outbox: exactly the PENDING -> QUEUED enqueue edge.
    "apps/webapp/src/webapp/services/job_dispatch.py": 1,
    # The run-request edge: shootout DRAFT -> PENDING at the process trigger.
    "apps/webapp/src/webapp/api/v1/shootouts.py": 1,
    # --- Legacy writers, shrink only ---
    # DOM-terminal-writer-routing: admin cancel + admin retry.
    "apps/webapp/src/webapp/api/admin.py": 2,
    # DOM-terminal-writer-routing: user retry.
    "apps/webapp/src/webapp/api/v1/jobs.py": 1,
    # JOB-idempotent-consume + DOM-shootout-finalise: claim, complete, fail,
    # and the master path's rogue parent/shootout projection.
    "apps/audio_worker/src/audio_worker/consumer.py": 8,
    # JOB-idempotent-consume: orchestrator claim + fan-out dispatch flips.
    "apps/shootout_orchestrator/src/shootout_orchestrator/consumer.py": 3,
    # DOM-reaper-render-race + DOM-terminal-writer-routing: raw-SQL reaper and
    # retry sweep writes.
    "apps/t3k_sync/src/t3k_sync/tasks.py": 3,
}

SCAN_ROOTS = ("apps", "model", "infra", "sources")


def _count_status_writes() -> Counter[str]:
    counts: Counter[str] = Counter()
    for root in SCAN_ROOTS:
        for path in sorted((REPO / root).rglob("*.py")):
            if "/tests/" in str(path):
                continue
            text = path.read_text(encoding="utf-8")
            hits = len(ORM_WRITE.findall(text)) + len(RAW_WRITE.findall(text))
            if hits:
                counts[str(path.relative_to(REPO))] = hits
    return counts


def test_status_writers_match_allowlist_exactly() -> None:
    actual = _count_status_writes()

    unexpected = {f: c for f, c in actual.items() if f not in ALLOWED}
    assert not unexpected, (
        "New direct Job.status/Shootout.status writer(s) found - route them "
        f"through webapp.services.job_transitions instead: {unexpected}"
    )

    grown = {f: (c, ALLOWED[f]) for f, c in actual.items() if c > ALLOWED[f]}
    assert not grown, (
        "Legacy status writer(s) grew - the allowlist is a ratchet; add no new "
        f"direct writes (actual vs allowed): {grown}"
    )

    stale = {f: (actual.get(f, 0), c) for f, c in ALLOWED.items() if actual.get(f, 0) != c}
    assert not stale, (
        "Status-writer allowlist is stale - a migration shrank (or a refactor "
        "moved) sanctioned writes; update ALLOWED to the new exact counts "
        f"(actual vs allowed): {stale}"
    )
