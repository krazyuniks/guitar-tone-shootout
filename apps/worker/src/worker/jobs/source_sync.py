"""SOURCE_SYNC Job Handler.

This module provides the SOURCE_SYNC job handler that orchestrates
T3K catalog synchronisation by creating sync services and running
the catalog sync process.
"""

from uuid import UUID

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.services.sync_service import T3KSyncService
from worker.db import get_t3k_session
from worker.main import broker


@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    """Handle SOURCE_SYNC job by creating T3K sync service and running catalog sync.

    This job:
    1. Creates T3K session for database access
    2. Instantiates API client, OAuth manager, and publisher
    3. Creates T3K sync service with dependencies
    4. Runs catalog sync process via run_catalog_sync

    Args:
        job_id: The ID of the SOURCE_SYNC job
    """
    async with get_t3k_session() as session:
        # Create T3K dependencies
        api_client = T3KAPIClient()
        publisher = GearSyncPublisher()

        # Create sync service
        sync_service = T3KSyncService(api_client=api_client, session=session)

        # Run catalog sync with publisher
        await sync_service.run_catalog_sync(publisher)


# Add task_id attribute for TaskIQ compatibility
handle_source_sync.task_id = handle_source_sync.task_name  # type: ignore[attr-defined]
