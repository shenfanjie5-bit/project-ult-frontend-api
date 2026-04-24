"""Shared API response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceArtifact(BaseModel):
    kind: str
    path: str
    exists: bool
    message: str | None = None


class StatusCounts(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    total: int = 0


class ServiceIdentity(BaseModel):
    module_id: str
    version: str
    mode: str
    active_profile: str


JsonDict = dict[str, Any]
