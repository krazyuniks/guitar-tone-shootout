from pydantic import BaseModel, ConfigDict


class AuthMeResponse(BaseModel):
    """Current authenticated user response."""

    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    email: str | None
    avatar_url: str | None
