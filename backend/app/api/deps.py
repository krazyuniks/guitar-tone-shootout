"""Dependency injection for API endpoints.

Common dependencies used across API endpoints are defined here.
"""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, settings


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        The application settings instance.
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]

# Future dependencies:
# - get_db: AsyncSession dependency
# - get_current_user: User authentication dependency
# - get_redis: Redis client dependency
