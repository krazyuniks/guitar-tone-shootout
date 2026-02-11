"""GTS Scheduler Configuration.

Provides SchedulerSettings for Redis broker connection.
"""

from pydantic_settings import BaseSettings


class SchedulerSettings(BaseSettings):
    """Scheduler configuration settings.

    Loads from environment variables:
    - REDIS_URL: Redis connection URL for broker
    """

    redis_url: str
