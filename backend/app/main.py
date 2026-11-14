"""FastAPI application factory serving API routers and compiled React SPA."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import explore, frames, health, overlays, sessions, spectrum, targets
from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.pipeline.session import list_ready_presets


logger = logging.getLogger("kurinjikumaran")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build configured FastAPI application instance."""
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ready = list_ready_presets(cfg.spx_preset_dir)
        logger.info("KurinjiKumaraN SPHEREx backend ready; %d pre-baked presets: %s", len(ready), ready)
        yield

    app = FastAPI(
        title="KurinjiKumaraN — SPHEREx Discovery Flipbook",
        version=cfg.app_version,
        lifespan=lifespan,
    )
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.exception_handler(ExploreError)
    async def handle_explore_error(_req: Request, exc: ExploreError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    app.include_router(health.router)
    app.include_router(targets.router)
    app.include_router(explore.router)
    app.include_router(sessions.router)
    app.include_router(frames.router)
    app.include_router(spectrum.router)
    app.include_router(overlays.router)

    dist_dir = cfg.spx_frontend_dist
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"error_code": "NOT_FOUND", "message": f"Unknown API endpoint '/{full_path}'."},
                )
            candidate = (dist_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(dist_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist_dir / "index.html")

    return app
