from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import Settings, get_settings
from app.core.db import DatabaseManager
from app.core.scheduler import build_scheduler
from app.routers import admin, dashboard, export, lite, settings as settings_router, trackings, uploads
from app.services.lite_job_store import LiteJobStore
from app.services.status_mapping_service import StatusMappingService


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    database = DatabaseManager(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_directories()
        database.create_all()
        with database.session() as session:
            StatusMappingService(session).seed_defaults()
        app.state.settings = settings
        app.state.database = database
        app.state.lite_job_store = LiteJobStore()
        app.state.scheduler = build_scheduler(database, settings) if settings.enable_scheduler else None
        if app.state.scheduler:
            app.state.scheduler.start()
        yield
        if app.state.scheduler:
            app.state.scheduler.shutdown(wait=False)
        database.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(uploads.router, prefix=settings.api_prefix)
    app.include_router(lite.router, prefix=settings.api_prefix)
    app.include_router(trackings.router, prefix=settings.api_prefix)
    app.include_router(dashboard.router, prefix=settings.api_prefix)
    app.include_router(export.router, prefix=settings.api_prefix)
    app.include_router(settings_router.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    frontend_dist = settings.frontend_dist_dir
    if frontend_dist.exists():
        frontend_dist_resolved = frontend_dist.resolve()
        index_file = frontend_dist_resolved / "index.html"

        @app.get("/", include_in_schema=False)
        def root() -> FileResponse:
            return FileResponse(index_file)

        @app.get("/{frontend_path:path}", include_in_schema=False)
        def frontend_entry(frontend_path: str) -> FileResponse:
            requested_path = (frontend_dist_resolved / frontend_path).resolve()
            try:
                requested_path.relative_to(frontend_dist_resolved)
            except ValueError:
                return FileResponse(index_file)

            if frontend_path and requested_path.is_file():
                return FileResponse(requested_path)
            return FileResponse(index_file)
    else:
        @app.get("/")
        def root() -> JSONResponse:
            return JSONResponse(
                {
                    "message": "Frontend build not found. Run `npm run build` in frontend/ to enable static serving."
                }
            )

    return app


app = create_app()
