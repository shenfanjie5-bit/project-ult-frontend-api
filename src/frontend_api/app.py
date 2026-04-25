"""FastAPI app factory for frontend-api."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from frontend_api import __version__
from frontend_api.errors import register_exception_handlers
from frontend_api.routes.cycle import router as cycle_router
from frontend_api.routes.entity_data import router as entity_data_router
from frontend_api.routes.graph import router as graph_router
from frontend_api.routes.system import router as system_router
from frontend_api.settings import FrontendApiSettings


def create_app(settings: FrontendApiSettings | None = None) -> FastAPI:
    app_settings = settings or FrontendApiSettings.from_env()
    app = FastAPI(
        title="Project ULT Frontend API",
        version=__version__,
        description=(
            "Read-only Project ULT System, Cycle, Formal, Entity, Data, and Graph "
            "boundary."
        ),
    )
    app.state.settings = app_settings
    if app_settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_allow_origins,
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(cycle_router)
    app.include_router(entity_data_router)
    app.include_router(graph_router)
    return app


app = create_app()
