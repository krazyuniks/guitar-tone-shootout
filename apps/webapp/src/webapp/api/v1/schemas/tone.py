"""Pydantic schemas for tone search API responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

FrontendGear = Literal["amp", "full-rig", "pedal", "outboard", "ir"]
FrontendPlatform = Literal["nam", "ir", "aida-x"]
FrontendLicense = Literal[
    "cc-by",
    "cc-by-sa",
    "cc-by-nc",
    "cc-by-nc-sa",
    "cc-by-nd",
    "cc-by-nc-nd",
    "cc0",
    "custom",
    "t3k",
]


class TagResponse(BaseModel):
    """Response schema for tone tags."""

    id: int
    name: str


class MakeResponse(BaseModel):
    """Response schema for tone makes."""

    id: int
    name: str


class CreatorResponse(BaseModel):
    """Response schema for tone creator metadata."""

    id: str
    username: str
    avatar_url: str | None = None
    url: str | None = None


class ToneResponse(BaseModel):
    """Response schema matching the frontend Tone shape."""

    id: str
    title: str
    description: str | None
    gear: FrontendGear
    platform: FrontendPlatform
    tags: list[TagResponse]
    makes: list[MakeResponse]
    links: list[str]
    videos: list[str]
    images: list[str]
    models_count: int
    downloads_count: int
    favorites_count: int
    license: FrontendLicense | None
    creator: CreatorResponse | None
    created_at: datetime
    updated_at: datetime | None


class PaginatedTonesResponse(BaseModel):
    """Paginated tone search response."""

    data: list[ToneResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
