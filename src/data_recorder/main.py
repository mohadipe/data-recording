from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from data_recorder.api.routes_health import router as health_router
from data_recorder.api.routes_wizard import router as wizard_router
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
app.include_router(wizard_router)

# Mount static directory and PWA manifest
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/manifest.json", include_in_schema=False)
async def get_manifest() -> FileResponse:
    """Serve PWA Web App Manifest."""
    manifest_file = STATIC_DIR / "manifest.json"
    return FileResponse(manifest_file, media_type="application/manifest+json")


if __name__ == "__main__":
    uvicorn.run(
        "data_recorder.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
