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

_FORMAL_PAYLOAD_FORBIDDEN_KEYS = frozenset(
    {
        "source",
        "source_name",
        "source_run_id",
        "source_status",
        "source_provider",
        "source_interface_id",
        "raw_loaded_at",
        "submitted_at",
        "ingest_seq",
        "provider",
        "provider_id",
        "provider_name",
        "ts_code",
        "index_code",
    }
)
_LEGACY_PAYLOAD_FORBIDDEN_KEYS = _FORMAL_PAYLOAD_FORBIDDEN_KEYS
_MVP20_DECISION_TARGET_LIMIT = 20
_MVP20_DECISION_TARGET_ROLE = "decision_target"
_MVP20_CONTEXT_ONLY_ROLE = "context_only"
_MVP20_ROLE_KEYS = (
    "entity_role",
    "target_role",
    "mvp20_role",
    "mvp20_entity_role",
)


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
    formal_object = _adapter(request).get_formal_object(object_type)
    return _sanitize_formal_object_response(formal_object)


@project_router.get(
    "/formal/{object_type}/{cycle_id}",
    response_model=FormalObjectResponse,
)
def get_formal_object_for_cycle(
    request: Request,
    object_type: str,
    cycle_id: str,
) -> FormalObjectResponse:
    formal_object = _adapter(request).get_formal_object(object_type, cycle_id=cycle_id)
    return _sanitize_formal_object_response(formal_object)


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
    formal_object = _adapter(request).get_formal_object(object_type)
    return _sanitize_legacy_payload(formal_object.payload, object_type=object_type)


def _sanitize_legacy_payload(payload: Any, *, object_type: str | None = None) -> Any:
    return _sanitize_object_payload(payload, object_type=object_type)


def _sanitize_formal_object_response(
    formal_object: FormalObjectResponse,
) -> FormalObjectResponse:
    return formal_object.model_copy(
        update={
            "payload": _sanitize_object_payload(
                formal_object.payload,
                object_type=formal_object.object_type,
            ),
            "metadata": _sanitize_public_formal_payload(formal_object.metadata),
        }
    )


def _sanitize_object_payload(payload: Any, *, object_type: str | None) -> Any:
    sanitized = _sanitize_public_formal_payload(payload)
    if object_type == "recommendation_snapshot":
        return _sanitize_mvp20_recommendation_payload(sanitized)
    return sanitized


def _sanitize_public_formal_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: _sanitize_public_formal_payload(value)
            for key, value in payload.items()
            if not _is_formal_payload_forbidden_key(key)
        }
    if isinstance(payload, list):
        return [_sanitize_public_formal_payload(item) for item in payload]
    return payload


def _sanitize_mvp20_recommendation_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list):
        return payload

    filtered = [
        recommendation
        for recommendation in recommendations
        if _is_mvp20_decision_target_item(recommendation)
    ][:_MVP20_DECISION_TARGET_LIMIT]
    return {**payload, "recommendations": filtered}


def _is_mvp20_decision_target_item(item: Any) -> bool:
    return _mvp20_item_role(item) == _MVP20_DECISION_TARGET_ROLE


def _is_mvp20_context_only_item(item: Any) -> bool:
    return _mvp20_item_role(item) == _MVP20_CONTEXT_ONLY_ROLE


def _mvp20_item_role(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in _MVP20_ROLE_KEYS:
        role = _normalized_mvp20_role(item.get(key))
        if role is not None:
            return role
    for nested_key in ("metadata", "properties"):
        nested = item.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in _MVP20_ROLE_KEYS:
            role = _normalized_mvp20_role(nested.get(key))
            if role is not None:
                return role
    return None


def _normalized_mvp20_role(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {_MVP20_DECISION_TARGET_ROLE, _MVP20_CONTEXT_ONLY_ROLE}:
        return normalized
    return None


def _is_formal_payload_forbidden_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    return (
        normalized in _FORMAL_PAYLOAD_FORBIDDEN_KEYS
        or normalized.startswith("source")
        or normalized.startswith("provider")
        or "_source" in normalized
        or "_provider" in normalized
    )


router.include_router(project_router)
router.include_router(compat_router)
