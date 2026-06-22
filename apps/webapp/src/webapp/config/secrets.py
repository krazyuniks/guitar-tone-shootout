"""Secret configuration helpers."""

from __future__ import annotations

import os

DEV_SECRET_KEY = "dev-secret-key-change-in-production"
DEV_SECRET_KEYS = frozenset(
    {
        DEV_SECRET_KEY,
        "dev_secret_key_change_in_production",
    }
)
DEV_ENVIRONMENTS = frozenset({"development", "test", "local"})


def is_development_environment() -> bool:
    """Return whether default development secrets are allowed."""
    env = os.getenv("ENV") or os.getenv("ENVIRONMENT") or "production"
    return env.lower() in DEV_ENVIRONMENTS


def get_app_secret_key() -> str:
    """Return the application signing secret.

    Production must set a non-default secret explicitly. Development/test/local
    keep the historical default so local stacks and tests still boot without
    secret provisioning.
    """
    secret_key = os.getenv("SECRET_KEY")
    if secret_key and secret_key not in DEV_SECRET_KEYS:
        return secret_key
    if is_development_environment():
        return secret_key or DEV_SECRET_KEY
    raise RuntimeError("SECRET_KEY must be set to a non-default value outside development")
