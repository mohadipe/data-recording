"""Centralized Jinja2 template environment and context processors."""

from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from data_recorder.core.config import get_settings

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def version_context(request: Request) -> dict[str, Any]:
    """Context processor providing application version and build metadata to all templates."""
    settings = get_settings()
    raw_version = settings.APP_VERSION or "0.1.0"
    display_version = raw_version if raw_version.startswith("v") else f"v{raw_version}"
    return {
        "app_version": raw_version,
        "display_version": display_version,
        "build_commit": settings.BUILD_COMMIT,
        "build_date": settings.BUILD_DATE,
    }


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[version_context],
)

templates.env.globals["get_settings"] = get_settings
