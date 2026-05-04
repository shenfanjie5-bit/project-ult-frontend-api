"""Read-only Graph routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from frontend_api.adapters.graph_adapter import GraphReadAdapter
from frontend_api.schemas.graph import (
    Ex3GraphSignal,
    GraphImpactResponse,
    GraphPathsResponse,
    GraphSubgraphResponse,
)
from frontend_api.settings import FrontendApiSettings

router = APIRouter(prefix="/api/project-ult/graph", tags=["graph"])


def _adapter(request: Request) -> GraphReadAdapter:
    settings: FrontendApiSettings = request.app.state.settings
    return GraphReadAdapter(project_root=settings.project_root)


@router.get("/subgraph", response_model=GraphSubgraphResponse)
def get_subgraph(
    request: Request,
    seed: str,
    depth: int = Query(default=1, ge=0, le=4),
    limit: int = Query(default=50, ge=1, le=500),
) -> GraphSubgraphResponse:
    return _adapter(request).get_subgraph(seed=seed, depth=depth, limit=limit)


@router.get("/paths", response_model=GraphPathsResponse)
def get_paths(
    request: Request,
    seed: str,
    depth: int = Query(default=2, ge=0, le=4),
    limit: int = Query(default=20, ge=1, le=200),
    channel: str | None = None,
) -> GraphPathsResponse:
    return _adapter(request).get_paths(
        seed=seed,
        depth=depth,
        limit=limit,
        channel=channel,
    )


@router.get("/impact", response_model=GraphImpactResponse)
def get_impact(
    request: Request,
    entity_id: str,
    cycle_id: str | None = None,
) -> GraphImpactResponse:
    return _adapter(request).get_impact(entity_id=entity_id, cycle_id=cycle_id)


@router.get("/ex3-signals/{cycle_id}", response_model=list[Ex3GraphSignal])
def get_ex3_signals(
    request: Request,
    cycle_id: str,
) -> list[Ex3GraphSignal]:
    return _adapter(request).get_ex3_signals(cycle_id=cycle_id)
