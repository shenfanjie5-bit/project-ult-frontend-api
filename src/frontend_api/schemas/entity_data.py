"""Entity registry and data table response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from frontend_api.schemas.common import JsonDict, SourceArtifact


ReadSourceStatus = Literal["available", "unavailable"]


class EntitySearchItem(BaseModel):
    entity_id: str
    display_name: str | None = None
    entity_type: str | None = None
    aliases: list[str] = Field(default_factory=list)
    score: float | None = None
    metadata: JsonDict = Field(default_factory=dict)


class EntitySearchResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    total: int
    next_cursor: str | None = None
    items: list[EntitySearchItem]
    message: str | None = None


class EntityProfileResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    entity_id: str
    profile: JsonDict


class DataRowsResponse(BaseModel):
    source_status: ReadSourceStatus
    source: SourceArtifact
    table: str | None = None
    source_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None
    items: list[dict[str, Any]]
    message: str | None = None
