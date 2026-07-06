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

# Repo root resolved relative to this file: /app in the compose container,
# the checkout root on a bare CI runner. Never hardcode the container mount.
REPO = Path(__file__).resolve().parents[3]

# Any assignment to a .status attribute (enum literal or dynamic), excluding
# comparisons and the gts domain entities' own self.status transitions (the
# domain state machine is not an ORM write path).
ORM_WRITE = re.compile(r"(?<!self)\.status\s*=(?!=)")
# Raw-SQL writes that bypass the ORM entirely.
RAW_WRITE = re.compile(r"UPDATE\s+(?:core_jobs|core_shootouts)\s+SET\s+status", re.IGNORECASE)

# file (repo-relative) -> exact number of status writes sanctioned there.
ALLOWED: dict[str, int] = {
    # The transition service itself: transition_job, the parent-cancel
    # projection, and the reconcile_parent projection writes.
    "apps/webapp/src/webapp/services/job_transitions.py": 7,
    # The outbox: exactly the PENDING -> QUEUED enqueue edge.
    "apps/webapp/src/webapp/services/job_dispatch.py": 1,
    # The run-request edge: shootout DRAFT -> PENDING at the process trigger.
    "apps/webapp/src/webapp/api/v1/shootouts.py": 1,
    # The orchestrator's fan-out dispatch: an outbox site (send + QUEUED flip
    # in one transaction), kept beside its thick-payload command construction.
    "apps/shootout_orchestrator/src/shootout_orchestrator/consumer.py": 1,
    # --- Legacy writers, shrink only ---
    # DOM-shootout-finalise: the master path's shootout/parent COMPLETED
    # projection - the legacy publish gate the finalise job replaces.
    "apps/audio_worker/src/audio_worker/consumer.py": 2,
    # DOM-reaper-render-race: the raw-SQL stale-job reaper (both paths).
    "apps/t3k_sync/src/t3k_sync/tasks.py": 2,
    # Domain->ORM mapping in the shootout repository save path.
    "apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py": 1,
    # DEBT-backend-dead-modules: the unused job repository write path.
    "apps/webapp/src/webapp/adapters/persistence/repositories/job_repository.py": 1,
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
