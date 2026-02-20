"""Scheduler settings compatibility."""

from pydantic_settings import BaseSettings


class SchedulerSettings(BaseSettings):
    """Scheduler configuration settings."""

    redis_url: str
