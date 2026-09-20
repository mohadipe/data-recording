from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General App Settings
    APP_NAME: str = "data-recorder"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 9015
    LOG_LEVEL: str = "INFO"

    # MySQL Database Settings (Synology NAS)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME_VERBRAUCH: str = "verbrauch"
    DB_NAME_WERTPAPIERE: str = "wertpapiere"
    DB_NAME_HIBISCUS: str = "hibiscus"

    # External Integration Settings
    EBUSD_URL: str = "http://192.168.2.125:58888/data"
    PAPERLESS_API_URL: str = ""
    PAPERLESS_API_TOKEN: str = ""

    # Database Connection Override (e.g. for sqlite in tests)
    DATABASE_URL: str | None = None

    def get_database_url(self, schema: str = "verbrauch") -> str:
        """Constructs the SQLAlchemy connection URL for the given schema."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{schema}?charset=utf8mb4"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns a cached instance of application settings."""
    return Settings()
