"""Cycle, formal object, and manifest response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from frontend_api.schemas.common import JsonDict, SourceArtifact


ReadSourceStatus = Literal["available", "degraded", "unavailable"]


class CycleManifestSummary(BaseModel):
    manifest_ref: str | None = None
    published_at: str | None = None
    formal_table_snapshots: dict[str, Any] = Field(default_factory=dict)


class CycleRecord(BaseModel):
    cycle_id: str
    status: str | None = None
    cycle_date: str | None = None
    cutoff_submitted_at: str | None = None
    cutoff_ingest_seq: int | None = None
    candidate_count: int | None = None
    selection_frozen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    manifest: CycleManifestSummary | None = None
    metadata: JsonDict = Field(default_factory=dict)


class CycleListResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    total: int
    items: list[CycleRecord]
    message: str | None = None


class FormalObjectResponse(BaseModel):
    object_type: str
    cycle_id: str | None = None
    source_status: ReadSourceStatus
    source: SourceArtifact
    snapshot_id: str | int | None = None
    payload: Any = None
    metadata: JsonDict = Field(default_factory=dict)


class ManifestResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    cycle_id: str | None = None
    manifest_ref: str | None = None
    published_at: str | None = None
    formal_table_snapshots: dict[str, Any] = Field(default_factory=dict)
    payload: Any = None
    metadata: JsonDict = Field(default_factory=dict)
