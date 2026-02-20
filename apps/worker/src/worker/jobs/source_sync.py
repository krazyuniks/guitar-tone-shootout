"""Compatibility shim for SOURCE_SYNC TaskIQ task.

Sync execution now lives in the `t3k_sync` bounded-context app.
This module is kept only to preserve the worker admin enqueue path.
"""

from uuid import UUID

from t3k_sync.source_sync import _check_auth_gate as _t3k_check_auth_gate
from t3k_sync.source_sync import run_source_sync
from worker.main import broker


def _check_auth_gate(auth_file_path: str | None = None) -> None:
    """Compatibility wrapper for legacy unit tests and imports."""
    _t3k_check_auth_gate(auth_file_path)


@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    """Dispatch SOURCE_SYNC handling to the dedicated t3k-sync app code."""
    await run_source_sync(job_id)


# Add task_id attribute for TaskIQ compatibility
handle_source_sync.task_id = handle_source_sync.task_name  # type: ignore[attr-defined]
