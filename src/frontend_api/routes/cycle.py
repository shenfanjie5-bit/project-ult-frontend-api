"""Read-only Cycle/Formal routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from frontend_api.adapters.data_platform_adapter import DataPlatformReadAdapter
from frontend_api.schemas.cycle import (
    CycleListResponse,
    CycleRecord,
    FormalObjectResponse,
    ManifestResponse,
)
from frontend_api.settings import FrontendApiSettings

router = APIRouter(tags=["cycle"])
project_router = APIRouter(prefix="/api/project-ult", tags=["cycle"])
compat_router = APIRouter(prefix="/api", tags=["frontend-compat"])


def _adapter(request: Request) -> DataPlatformReadAdapter:
    settings: FrontendApiSettings = request.app.state.settings
    return DataPlatformReadAdapter(
        project_root=settings.project_root,
        allow_public_api_fallback=settings.allow_data_platform_public_api_fallback,
    )


@project_router.get("/cycles", response_model=CycleListResponse)
def get_cycles(request: Request) -> CycleListResponse:
    return _adapter(request).list_cycles()


@project_router.get("/cycles/{cycle_id}", response_model=CycleRecord)
def get_cycle(request: Request, cycle_id: str) -> CycleRecord:
    return _adapter(request).get_cycle(cycle_id)


@project_router.get("/formal/{object_type}", response_model=FormalObjectResponse)
def get_latest_formal_object(
    request: Request,
    object_type: str,
) -> FormalObjectResponse:
    return _adapter(request).get_formal_object(object_type)


@project_router.get(
    "/formal/{object_type}/{cycle_id}",
    response_model=FormalObjectResponse,
)
def get_formal_object_for_cycle(
    request: Request,
    object_type: str,
    cycle_id: str,
) -> FormalObjectResponse:
    return _adapter(request).get_formal_object(object_type, cycle_id=cycle_id)


@project_router.get("/manifests/latest", response_model=ManifestResponse)
def get_latest_manifest(request: Request) -> ManifestResponse:
    return _adapter(request).get_latest_manifest()


@compat_router.get("/world-state/latest")
def get_legacy_world_state(request: Request) -> Any:
    return _legacy_payload(request, "world_state_snapshot")


@compat_router.get("/pool/latest")
def get_legacy_pool(request: Request) -> Any:
    return _legacy_payload(request, "official_alpha_pool")


@compat_router.get("/recommendations/latest")
def get_legacy_recommendations(request: Request) -> Any:
    return _legacy_payload(request, "recommendation_snapshot")


def _legacy_payload(request: Request, object_type: str) -> Any:
    return _adapter(request).get_formal_object(object_type).payload


router.include_router(project_router)
router.include_router(compat_router)
