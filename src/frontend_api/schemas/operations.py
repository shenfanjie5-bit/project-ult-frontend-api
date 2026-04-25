"""Reasoner, audit, backtest, and orchestrator read-only schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from frontend_api.schemas.common import JsonDict, SourceArtifact


ReadSourceStatus = Literal["available", "unavailable"]


class ReadListResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    items: list[JsonDict]
    total: int
    next_cursor: str | None = None
    message: str | None = None


class ReadDetailResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    payload: JsonDict
    metadata: JsonDict = Field(default_factory=dict)
    message: str | None = None


class ReasonerProvidersResponse(ReadListResponse):
    pass


class ReasonerResultsResponse(ReadListResponse):
    pass


class AuditCycleResponse(ReadDetailResponse):
    pass


class ReplayCycleResponse(ReadDetailResponse):
    pass


class BacktestListResponse(ReadListResponse):
    pass


class BacktestDetailResponse(ReadDetailResponse):
    pass


class OrchestratorRunsResponse(ReadListResponse):
    pass


class OrchestratorRunDetailResponse(ReadDetailResponse):
    pass
