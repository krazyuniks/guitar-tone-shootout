"""Timing-constant invariants from docs/design/job-system-contract.md.

Pinning the ordering means nobody can tune one constant and silently break the
lease design: one missed beat must never cause redelivery, and a crashed
worker's message must redeliver before the reaper declares the job dead.
"""

import inspect

from audio.processing.chain_executor import execute_signal_chain
from messaging.consumer_base import (
    HEARTBEAT_INTERVAL_SECONDS,
    VT_EXTENSION_SECONDS,
    BaseConsumer,
)
from webapp.services.job_transitions import LEASE_THRESHOLD


def test_one_missed_beat_never_redelivers() -> None:
    assert HEARTBEAT_INTERVAL_SECONDS * 2 < VT_EXTENSION_SECONDS


def test_redelivery_precedes_reap() -> None:
    """A crashed worker's message redelivers before the lease is declared dead."""
    assert LEASE_THRESHOLD.total_seconds() > VT_EXTENSION_SECONDS


def test_initial_visibility_below_extension() -> None:
    """The first read's window is the floor; renewals only ever extend it."""
    import inspect as _inspect

    default_vt = _inspect.signature(BaseConsumer.__init__).parameters["visibility_timeout"].default
    assert default_vt <= VT_EXTENSION_SECONDS


def test_chain_executor_is_honestly_synchronous() -> None:
    """The render is CPU-bound sync DSP; async callers must offload it.

    Re-asyncifying it would silently block the event loop for whole renders
    (the pre-fix root cause of the reaper punishing healthy work).
    """
    assert not inspect.iscoroutinefunction(execute_signal_chain)
