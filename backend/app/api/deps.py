"""Dependency injection for API endpoints.

Common dependencies used across API endpoints are defined here.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.database import get_db


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        The application settings instance.
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Future dependencies:
# - get_current_user: User authentication dependency
# - get_redis: Redis client dependency
