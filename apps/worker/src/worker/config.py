"""Worker configuration settings.

Loads configuration from environment variables for Redis broker and the single
gts_core database connection.
"""

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    """Worker configuration loaded from environment variables.

    Attributes:
        redis_url: Redis connection URL for TaskIQ broker
        database_url: PostgreSQL connection URL for gts_core database
    """

    redis_url: str
    database_url: str
