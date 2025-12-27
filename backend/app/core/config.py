"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Guitar Tone Shootout"
    debug: bool = False
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:4321"

    # Database
    database_url: str = "postgresql+asyncpg://shootout:devpassword@db:5432/shootout"

    # Redis
    redis_url: str = "redis://redis:6379"

    # CORS
    cors_origins: list[str] = ["http://localhost:4321", "http://localhost:3000"]

    # Tone 3000 OAuth
    tone3000_client_id: str = ""
    tone3000_client_secret: str = ""
    tone3000_redirect_uri: str = "http://localhost:8000/auth/callback"

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Model cache
    model_cache_dir: str = "/data/models/cache"
    model_cache_max_age_days: int = 30

    # File uploads
    upload_dir: str = "/data/uploads"


settings = Settings()
