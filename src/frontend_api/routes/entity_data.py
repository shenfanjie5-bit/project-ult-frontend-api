"""Read-only Entity/Data routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from frontend_api.adapters.entity_data_adapter import EntityDataReadAdapter
from frontend_api.schemas.entity_data import (
    DataRowsResponse,
    EntityProfileResponse,
    EntitySearchResponse,
)
from frontend_api.settings import FrontendApiSettings

router = APIRouter(prefix="/api/project-ult", tags=["entity-data"])


def _adapter(request: Request) -> EntityDataReadAdapter:
    settings: FrontendApiSettings = request.app.state.settings
    return EntityDataReadAdapter(project_root=settings.project_root)


@router.get("/entities/search", response_model=EntitySearchResponse)
def search_entities(
    request: Request,
    q: str = "",
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
) -> EntitySearchResponse:
    return _adapter(request).search_entities(query=q, limit=limit, cursor=cursor)


@router.get("/entities/{entity_id}", response_model=EntityProfileResponse)
def get_entity_profile(request: Request, entity_id: str) -> EntityProfileResponse:
    return _adapter(request).get_entity_profile(entity_id)


@router.get("/data/canonical/{table}", response_model=DataRowsResponse)
def get_canonical_rows(
    request: Request,
    table: str,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
) -> DataRowsResponse:
    return _adapter(request).read_canonical_table(
        table,
        limit=limit,
        cursor=cursor,
    )


@router.get("/data/raw/{source}", response_model=DataRowsResponse)
def get_raw_rows(
    request: Request,
    source: str,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
) -> DataRowsResponse:
    return _adapter(request).read_raw_source(source, limit=limit, cursor=cursor)
