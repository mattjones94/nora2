from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration supplied through container environment variables."""

    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str
    mysql_user: str
    mysql_password: str

    qdrant_url: str = "http://qdrant:6333"

    model_config = SettingsConfigDict(
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()