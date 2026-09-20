from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from data_recorder.api.routes_health import router as health_router
from data_recorder.core.config import get_settings
from data_recorder.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown events."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include API routers
app.include_router(health_router)


if __name__ == "__main__":
    uvicorn.run(
        "data_recorder.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
