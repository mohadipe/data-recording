import os
import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_app_version() -> str:
    """Dynamically resolves the application version.

    Priority:
    1. APP_VERSION environment variable
    2. importlib.metadata from installed package ('data-recorder')
    3. pyproject.toml in repository root
    4. data_recorder.__version__
    5. Fallback '0.1.0'
    """
    if env_version := os.getenv("APP_VERSION"):
        return env_version

    try:
        return version("data-recorder")
    except (PackageNotFoundError, Exception):
        pass

    try:
        pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if pyproject_path.is_file():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                if "project" in data and "version" in data["project"]:
                    return str(data["project"]["version"])
    except Exception:
        pass

    try:
        import data_recorder

        if hasattr(data_recorder, "__version__"):
            return str(data_recorder.__version__)
    except Exception:
        pass

    return "0.1.0"


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
    APP_VERSION: str = Field(default_factory=get_app_version)
    BUILD_COMMIT: str | None = None
    BUILD_DATE: str | None = None
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 9015
    LOG_LEVEL: str = "INFO"

    @field_validator("APP_VERSION", mode="before")
    @classmethod
    def validate_app_version(cls, v: Any) -> str:
        if not v:
            return get_app_version()
        return str(v)

    @field_validator("BUILD_COMMIT", "BUILD_DATE", mode="before")
    @classmethod
    def clean_empty_build_info(cls, v: Any) -> str | None:
        if not v:
            return None
        return str(v)

    # MySQL Database Settings (Synology NAS)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME_VERBRAUCH: str = "verbrauch"
    DB_NAME_WERTPAPIERE: str = "wertpapiere"
    DB_NAME_HIBISCUS: str = "hibiscus"
    HIBISCUS_ACCOUNT_FILTERS: str = ""

    # External Integration Settings
    EBUSD_URL: str = "http://192.168.2.125:58888/data"
    PAPERLESS_API_URL: str = ""
    PAPERLESS_API_TOKEN: str = ""
    PAPERLESS_TAG: str = "Zaehlerbeleg"
    PAPERLESS_DOCUMENT_TYPE: str = "Zaehlerbeleg"
    FAILED_UPLOADS_DIR: str = "data/failed_uploads"
    SHARED_UPLOADS_DIR: str = "data/shared_uploads"

    # Heating Oil Scraper Settings (PLZ 90579, 2500L)
    HEIZOEL_PLZ: str = "90579"
    HEIZOEL_MENGE_LITER: int = 2500
    HEIZOEL_PROVIDER_URL: str = "https://www.esyoil.com/heizoelpreise/heizoel-bestellung"
    HEIZOEL_SCRAPER_TIMEOUT: float = 15.0
    HEIZOEL_SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

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
