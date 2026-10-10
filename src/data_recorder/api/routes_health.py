from fastapi import APIRouter
from pydantic import BaseModel

from data_recorder.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    app_name: str
    commit: str | None = None
    build_date: str | None = None


class SystemVersionResponse(BaseModel):
    app_name: str
    version: str
    commit: str | None = None
    build_date: str | None = None
    environment: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns the application health status and current version."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        app_name=settings.APP_NAME,
        commit=settings.BUILD_COMMIT,
        build_date=settings.BUILD_DATE,
    )


@router.get("/api/system/version", response_model=SystemVersionResponse)
def get_system_version() -> SystemVersionResponse:
    """Returns structured system and version information for monitoring."""
    settings = get_settings()
    return SystemVersionResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        commit=settings.BUILD_COMMIT,
        build_date=settings.BUILD_DATE,
        environment=settings.ENVIRONMENT,
    )
