"""Read-only System/Assembly routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from frontend_api.adapters.assembly_adapter import AssemblyAdapter
from frontend_api.schemas.system import (
    CompatibilityResponse,
    HealthResponse,
    ModulesResponse,
    ProfilesResponse,
)
from frontend_api.settings import FrontendApiSettings

router = APIRouter(prefix="/api/project-ult", tags=["system"])


def _adapter(request: Request) -> AssemblyAdapter:
    settings: FrontendApiSettings = request.app.state.settings
    return AssemblyAdapter(
        project_root=settings.project_root,
        active_profile=settings.profile,
        mode=settings.mode,
    )


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    return _adapter(request).health()


@router.get("/modules", response_model=ModulesResponse)
def get_modules(request: Request) -> ModulesResponse:
    return _adapter(request).list_modules()


@router.get("/profiles", response_model=ProfilesResponse)
def get_profiles(request: Request) -> ProfilesResponse:
    return _adapter(request).list_profiles()


@router.get("/compat", response_model=CompatibilityResponse)
def get_compatibility(request: Request) -> CompatibilityResponse:
    return _adapter(request).list_compatibility()
