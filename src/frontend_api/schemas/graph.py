"""Graph read-only response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from frontend_api.schemas.common import JsonDict, SourceArtifact


GraphSourceStatus = Literal["available", "unavailable"]
Mvp20EntityRole = Literal["decision_target", "context_only"]


class GraphSubgraphQuery(BaseModel):
    seed: str
    depth: int
    limit: int


class GraphPathsQuery(BaseModel):
    seed: str
    depth: int
    limit: int
    channel: str | None = None


class GraphImpactQuery(BaseModel):
    entity_id: str
    cycle_id: str | None = None


class GraphNode(BaseModel):
    node_id: str
    label: str | None = None
    entity_id: str | None = None
    entity_role: Mvp20EntityRole | None = None
    display_name: str | None = None
    properties: JsonDict = Field(default_factory=dict)
    metadata: JsonDict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    channel: str | None = None
    source_entity_role: Mvp20EntityRole | None = None
    target_entity_role: Mvp20EntityRole | None = None
    weight: float | None = None
    properties: JsonDict = Field(default_factory=dict)
    metadata: JsonDict = Field(default_factory=dict)


class GraphPath(BaseModel):
    path_id: str
    seed: str
    target: str
    target_role: Mvp20EntityRole | None = None
    nodes: list[str]
    edges: list[str]
    depth: int
    channel: str | None = None
    score: float | None = None
    summary: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class GraphImpactItem(BaseModel):
    entity_id: str
    entity_role: Mvp20EntityRole | None = None
    display_name: str | None = None
    impact_score: float | None = None
    channels: list[str] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)


class Ex3GraphSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_id: str
    candidate_id: int
    delta_id: str
    delta_type: str
    selection_ref: str
    source_node: str
    target_node: str
    relation_type: str
    properties: JsonDict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class GraphSubgraphResponse(BaseModel):
    source_status: GraphSourceStatus
    source: SourceArtifact
    query: GraphSubgraphQuery
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int
    truncated: bool
    message: str | None = None


class GraphPathsResponse(BaseModel):
    source_status: GraphSourceStatus
    source: SourceArtifact
    query: GraphPathsQuery
    paths: list[GraphPath]
    total: int
    truncated: bool
    message: str | None = None


class GraphImpactResponse(BaseModel):
    source_status: GraphSourceStatus
    source: SourceArtifact
    query: GraphImpactQuery
    items: list[GraphImpactItem]
    impacted_entities: list[GraphImpactItem]
    total: int
    snapshot_id: str | None = None
    message: str | None = None


JsonGraphObject = dict[str, Any]
