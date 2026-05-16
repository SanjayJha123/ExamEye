"""FastAPI application wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .database import init_db
from .routes import alerts as alerts_routes
from .routes import frames as frames_routes
from .routes import pages as pages_routes
from .routes import query as query_routes
from .routes import summaries as summaries_routes
from .routes import videos as videos_routes

_BASE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(_BASE / "templates"))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ExamEye", version="0.1.0", lifespan=_lifespan)

    app.state.templates = TEMPLATES
    app.state.settings = settings

    app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
    app.mount("/media/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")
    app.mount("/media/frames", StaticFiles(directory=str(settings.frame_dir)), name="frames")

    app.include_router(pages_routes.router)
    app.include_router(videos_routes.router)
    app.include_router(frames_routes.router)
    app.include_router(summaries_routes.router)
    app.include_router(query_routes.router)
    app.include_router(alerts_routes.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
