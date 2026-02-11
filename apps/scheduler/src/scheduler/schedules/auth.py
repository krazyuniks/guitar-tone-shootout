"""Scheduled tasks for T3K OAuth token refresh.

This module defines scheduled tasks that run periodically to:
- Refresh T3K OAuth tokens for all users
"""

import os

from source_t3k.adapters.inbound.oauth import T3KOAuthManager
from worker.db import get_t3k_session


class _Schedule:
    """Schedule configuration for TaskIQ.

    Attributes:
        seconds: Interval in seconds
    """

    def __init__(self, seconds: int) -> None:
        """Initialize schedule.

        Args:
            seconds: Interval in seconds
        """
        self.seconds = seconds


async def refresh_t3k_tokens() -> None:
    """Refresh T3K OAuth tokens for all users.

    Creates OAuth manager with T3K session and config from environment,
    then calls refresh_token to update all expired tokens in the database.
    """
    # Get environment configuration
    encryption_key = os.getenv("T3K_TOKEN_ENCRYPTION_KEY", "")
    client_id = os.getenv("T3K_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("T3K_OAUTH_CLIENT_SECRET", "")
    oauth_base_url = os.getenv("T3K_OAUTH_BASE_URL", "")

    async with get_t3k_session() as session:
        # Create OAuth manager
        oauth_manager = T3KOAuthManager(
            session=session,
            encryption_key=encryption_key,
            client_id=client_id,
            client_secret=client_secret,
            oauth_base_url=oauth_base_url,
        )

        # Refresh tokens (commits internally)
        await oauth_manager.refresh_token()


# Attach labels to functions for TaskIQ discovery
# 12 hours = 43200 seconds
refresh_t3k_tokens.labels = {"schedule": [_Schedule(43200)]}  # type: ignore[attr-defined]
