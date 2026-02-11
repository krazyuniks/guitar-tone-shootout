"""Worker configuration settings.

Loads configuration from environment variables for Redis broker and database
connections.
"""

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    """Worker configuration loaded from environment variables.

    Attributes:
        redis_url: Redis connection URL for TaskIQ broker
        database_url: PostgreSQL connection URL for gts_core database
        t3k_database_url: PostgreSQL connection URL for gts_t3k_source database
    """

    redis_url: str
    database_url: str
    t3k_database_url: str
