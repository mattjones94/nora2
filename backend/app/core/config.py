from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration supplied through container environment variables."""

    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str
    mysql_user: str
    mysql_password: str

    qdrant_url: str = "http://qdrant:6333"

    conversation_expiration_sweep_interval_seconds: int = Field(
        default=60,
        ge=5,
        le=3600,
    )

    conversation_expiration_sweep_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
    )

    model_config = SettingsConfigDict(
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application configuration."""

    return Settings()