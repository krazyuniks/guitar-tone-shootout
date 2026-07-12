"""Visibility of a shootout independently of its processing status."""

from enum import Enum


class ShootoutVisibility(str, Enum):
    """Who may discover or open a shootout."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
