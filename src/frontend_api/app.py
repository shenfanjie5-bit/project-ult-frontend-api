"""FastAPI app factory for frontend-api."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from frontend_api import __version__
from frontend_api.errors import register_exception_handlers
from frontend_api.routes.cycle import router as cycle_router
from frontend_api.routes.entity_data import (
    debug_router as entity_data_debug_router,
    router as entity_data_router,
)
from frontend_api.routes.graph import router as graph_router
from frontend_api.routes.operations import router as operations_router
from frontend_api.routes.system import router as system_router
from frontend_api.settings import FrontendApiSettings


def create_app(settings: FrontendApiSettings | None = None) -> FastAPI:
    app_settings = settings or FrontendApiSettings.from_env()
    # H3 deployment guard: refuse to construct an unauthenticated app on
    # a non-loopback host unless the operator opted out (signals upstream
    # auth proxy). See FrontendApiSettings.assert_safe_to_serve.
    app_settings.assert_safe_to_serve()
    app = FastAPI(
        title="Project ULT Frontend API",
        version=__version__,
        description=(
            "Read-only Project ULT System, Cycle, Formal, Entity, Data, Graph, "
            "Reasoner, Audit, and Orchestrator boundary."
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
    if app_settings.enable_raw_debug_routes:
        app.include_router(entity_data_debug_router)
    app.include_router(graph_router)
    app.include_router(operations_router)
    return app
