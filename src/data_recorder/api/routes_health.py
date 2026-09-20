from fastapi import APIRouter
from pydantic import BaseModel

from data_recorder.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    app_name: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns the application health status and current version."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        app_name=settings.APP_NAME,
    )
