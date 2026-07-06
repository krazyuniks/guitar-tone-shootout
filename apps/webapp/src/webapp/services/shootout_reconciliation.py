"""Session-owning wrapper for parent reconciliation, shared by the workers.

The projection logic lives in webapp.services.job_transitions (the single
transition service); this wrapper exists for callers that hold no session -
the audio worker and the shootout orchestrator - and preserves their
call shape: reconcile_parent_after_audio(parent_job_id, database_url).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from messaging.db import get_session_no_tx as get_session
from webapp.services.job_transitions import reconcile_parent

if TYPE_CHECKING:
    from uuid import UUID


async def reconcile_parent_after_audio(parent_job_id: UUID, database_url: str) -> None:
    """Reconcile parent SHOOTOUT state from child SHOOTOUT_AUDIO results."""
    async with get_session(database_url) as session:
        await reconcile_parent(session, parent_job_id)
        await session.commit()
