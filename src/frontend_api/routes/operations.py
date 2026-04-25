"""Read-only Reasoner, Audit, Backtest, and Orchestrator routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from frontend_api.adapters.operations_adapter import OperationsReadAdapter
from frontend_api.schemas.operations import (
    AuditCycleResponse,
    BacktestDetailResponse,
    BacktestListResponse,
    OrchestratorRunDetailResponse,
    OrchestratorRunsResponse,
    ReasonerProvidersResponse,
    ReasonerResultsResponse,
    ReplayCycleResponse,
)
from frontend_api.settings import FrontendApiSettings

router = APIRouter(prefix="/api/project-ult", tags=["operations"])


def _adapter(request: Request) -> OperationsReadAdapter:
    settings: FrontendApiSettings = request.app.state.settings
    return OperationsReadAdapter(project_root=settings.project_root)


@router.get("/reasoner/providers", response_model=ReasonerProvidersResponse)
def list_reasoner_providers(request: Request) -> ReasonerProvidersResponse:
    return _adapter(request).list_reasoner_providers()


@router.get("/reasoner/results", response_model=ReasonerResultsResponse)
def list_reasoner_results(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
    cycle_id: str | None = None,
) -> ReasonerResultsResponse:
    return _adapter(request).list_reasoner_results(
        limit=limit,
        cursor=cursor,
        cycle_id=cycle_id,
    )


@router.get("/audit/{cycle_id}", response_model=AuditCycleResponse)
def get_audit(request: Request, cycle_id: str) -> AuditCycleResponse:
    return _adapter(request).get_audit(cycle_id)


@router.get("/replay/{cycle_id}", response_model=ReplayCycleResponse)
def get_replay(request: Request, cycle_id: str) -> ReplayCycleResponse:
    return _adapter(request).get_replay(cycle_id)


@router.get("/backtests", response_model=BacktestListResponse)
def list_backtests(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
) -> BacktestListResponse:
    return _adapter(request).list_backtests(limit=limit, cursor=cursor)


@router.get("/backtests/{backtest_id}", response_model=BacktestDetailResponse)
def get_backtest(
    request: Request,
    backtest_id: str,
) -> BacktestDetailResponse:
    return _adapter(request).get_backtest(backtest_id)


@router.get("/orchestrator/runs", response_model=OrchestratorRunsResponse)
def list_orchestrator_runs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = None,
    status: str | None = None,
) -> OrchestratorRunsResponse:
    return _adapter(request).list_orchestrator_runs(
        limit=limit,
        cursor=cursor,
        status=status,
    )


@router.get(
    "/orchestrator/runs/{run_id}",
    response_model=OrchestratorRunDetailResponse,
)
def get_orchestrator_run(
    request: Request,
    run_id: str,
) -> OrchestratorRunDetailResponse:
    return _adapter(request).get_orchestrator_run(run_id)
