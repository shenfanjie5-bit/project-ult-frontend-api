"""Read-only adapter for graph-engine frontend-api artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import SourceArtifact
from frontend_api.schemas.graph import (
    GraphEdge,
    GraphImpactItem,
    GraphImpactQuery,
    GraphImpactResponse,
    GraphNode,
    GraphPath,
    GraphPathsQuery,
    GraphPathsResponse,
    GraphSubgraphQuery,
    GraphSubgraphResponse,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

_GRAPH_ARTIFACT_ROOT = ("graph-engine", "artifacts", "frontend-api")
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_CHANNEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class GraphReadAdapter:
    """Read graph-engine frontend-api artifacts without importing graph-engine."""

    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.artifact_root = self.project_root.joinpath(*_GRAPH_ARTIFACT_ROOT)

    def get_subgraph(
        self,
        *,
        seed: str,
        depth: int,
        limit: int,
    ) -> GraphSubgraphResponse:
        validated_seed = self._validate_token(seed, "seed")
        query = GraphSubgraphQuery(seed=validated_seed, depth=depth, limit=limit)
        path = self.artifact_root / "subgraph.json"
        if not path.exists():
            return GraphSubgraphResponse(
                source_status="unavailable",
                source=self._unavailable_source(
                    "graph_subgraph",
                    path,
                    "graph-engine frontend-api subgraph artifact not found",
                ),
                query=query,
                nodes=[],
                edges=[],
                total_nodes=0,
                total_edges=0,
                truncated=False,
                message="graph-engine subgraph artifact source unavailable",
            )

        raw = self._load_mapping(path)
        raw_nodes = self._required_list(raw, "nodes", path=path)
        raw_edges = self._required_list(raw, "edges", path=path)
        nodes = [
            self._validate_model(
                GraphNode,
                self._require_mapping(node, path=path, key="nodes", index=index),
                path=path,
                key="nodes",
                index=index,
            )
            for index, node in enumerate(raw_nodes)
        ]
        edges = [
            self._validate_model(
                GraphEdge,
                self._require_mapping(edge, path=path, key="edges", index=index),
                path=path,
                key="edges",
                index=index,
            )
            for index, edge in enumerate(raw_edges)
        ]

        filtered_nodes, filtered_edges = self._subgraph_for_seed(
            nodes,
            edges,
            seed=validated_seed,
            depth=depth,
        )
        total_nodes = len(filtered_nodes)
        total_edges = len(filtered_edges)
        page_nodes = filtered_nodes[:limit]
        included_node_ids = {node.node_id for node in page_nodes}
        page_edges = [
            edge
            for edge in filtered_edges
            if (
                edge.source_node_id in included_node_ids
                and edge.target_node_id in included_node_ids
            )
        ][:limit]
        truncated = total_nodes > len(page_nodes) or total_edges > len(page_edges)

        return GraphSubgraphResponse(
            source_status="available",
            source=self._artifact_source("graph_subgraph", path),
            query=query,
            nodes=page_nodes,
            edges=page_edges,
            total_nodes=total_nodes,
            total_edges=total_edges,
            truncated=truncated,
        )

    def get_paths(
        self,
        *,
        seed: str,
        depth: int,
        limit: int,
        channel: str | None,
    ) -> GraphPathsResponse:
        validated_seed = self._validate_token(seed, "seed")
        validated_channel = self._validate_channel(channel)
        query = GraphPathsQuery(
            seed=validated_seed,
            depth=depth,
            limit=limit,
            channel=validated_channel,
        )
        path = self.artifact_root / "paths.json"
        if not path.exists():
            return GraphPathsResponse(
                source_status="unavailable",
                source=self._unavailable_source(
                    "graph_paths",
                    path,
                    "graph-engine frontend-api paths artifact not found",
                ),
                query=query,
                paths=[],
                total=0,
                truncated=False,
                message="graph-engine paths artifact source unavailable",
            )

        raw = self._load_mapping(path)
        raw_paths = self._required_list(raw, "paths", path=path)
        paths = [
            self._validate_model(
                GraphPath,
                self._require_mapping(item, path=path, key="paths", index=index),
                path=path,
                key="paths",
                index=index,
            )
            for index, item in enumerate(raw_paths)
        ]
        filtered_paths = [
            item
            for item in paths
            if item.seed == validated_seed
            and item.depth <= depth
            and (validated_channel is None or item.channel == validated_channel)
        ]
        page = filtered_paths[:limit]
        return GraphPathsResponse(
            source_status="available",
            source=self._artifact_source("graph_paths", path),
            query=query,
            paths=page,
            total=len(filtered_paths),
            truncated=len(filtered_paths) > len(page),
        )

    def get_impact(
        self,
        *,
        entity_id: str,
        cycle_id: str | None,
    ) -> GraphImpactResponse:
        validated_entity_id = self._validate_token(entity_id, "entity_id")
        validated_cycle_id = self._validate_optional_token(cycle_id, "cycle_id")
        query = GraphImpactQuery(
            entity_id=validated_entity_id,
            cycle_id=validated_cycle_id,
        )
        path = self.artifact_root / "impact.json"
        if not path.exists():
            return GraphImpactResponse(
                source_status="unavailable",
                source=self._unavailable_source(
                    "graph_impact",
                    path,
                    "graph-engine frontend-api impact artifact not found",
                ),
                query=query,
                items=[],
                impacted_entities=[],
                total=0,
                snapshot_id=None,
                message="graph-engine impact artifact source unavailable",
            )

        raw = self._load_mapping(path)
        artifact_entity_id = raw.get("entity_id")
        if not isinstance(artifact_entity_id, str) or not artifact_entity_id:
            self._raise_schema_error(
                "impact artifact entity_id must be a non-empty string",
                path=path,
                details={"actual_type": type(artifact_entity_id).__name__},
            )
        artifact_cycle_id = raw.get("cycle_id")
        if artifact_cycle_id is not None and not isinstance(artifact_cycle_id, str):
            self._raise_schema_error(
                "impact artifact cycle_id must be a string when present",
                path=path,
                details={"actual_type": type(artifact_cycle_id).__name__},
            )
        snapshot_id = raw.get("snapshot_id")
        if snapshot_id is not None and not isinstance(snapshot_id, str):
            self._raise_schema_error(
                "impact artifact snapshot_id must be a string when present",
                path=path,
                details={"actual_type": type(snapshot_id).__name__},
            )

        if artifact_entity_id != validated_entity_id or (
            validated_cycle_id is not None and artifact_cycle_id != validated_cycle_id
        ):
            return GraphImpactResponse(
                source_status="available",
                source=self._artifact_source("graph_impact", path),
                query=query,
                items=[],
                impacted_entities=[],
                total=0,
                snapshot_id=snapshot_id,
            )

        raw_items = self._required_list(raw, "items", path=path)
        items = [
            self._validate_model(
                GraphImpactItem,
                self._require_mapping(item, path=path, key="items", index=index),
                path=path,
                key="items",
                index=index,
            )
            for index, item in enumerate(raw_items)
        ]
        return GraphImpactResponse(
            source_status="available",
            source=self._artifact_source("graph_impact", path),
            query=query,
            items=items,
            impacted_entities=items,
            total=len(items),
            snapshot_id=snapshot_id,
        )

    def _subgraph_for_seed(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        *,
        seed: str,
        depth: int,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes_by_id = {node.node_id: node for node in nodes}
        matched_seed_ids = [
            node.node_id
            for node in nodes
            if node.node_id == seed or node.entity_id == seed
        ]
        if not matched_seed_ids:
            return [], []

        reached = set(matched_seed_ids)
        selected_edges: list[GraphEdge] = []
        frontier = set(matched_seed_ids)
        for _ in range(depth):
            next_frontier: set[str] = set()
            for edge in edges:
                touches_frontier = (
                    edge.source_node_id in frontier or edge.target_node_id in frontier
                )
                if not touches_frontier:
                    continue
                if edge not in selected_edges:
                    selected_edges.append(edge)
                for node_id in (edge.source_node_id, edge.target_node_id):
                    if node_id not in reached:
                        reached.add(node_id)
                        next_frontier.add(node_id)
            frontier = next_frontier
            if not frontier:
                break

        selected_nodes = [node for node in nodes if node.node_id in reached]
        selected_edges = [
            edge
            for edge in selected_edges
            if edge.source_node_id in nodes_by_id and edge.target_node_id in nodes_by_id
        ]
        return selected_nodes, selected_edges

    def _load_mapping(self, path: Path) -> Mapping[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectUltApiError(
                "PROJECT_ULT_GRAPH_ARTIFACT_SCHEMA_INVALID",
                "Invalid JSON artifact",
                status_code=500,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise ProjectUltApiError(
                "PROJECT_ULT_GRAPH_ARTIFACT_UNAVAILABLE",
                "Cannot read graph artifact",
                status_code=503,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        if not isinstance(raw, Mapping):
            self._raise_schema_error(
                "graph artifact root must be an object",
                path=path,
                details={"actual_type": type(raw).__name__},
            )
        return raw

    def _required_list(
        self,
        raw: Mapping[str, Any],
        key: str,
        *,
        path: Path,
    ) -> Sequence[Any]:
        value = raw.get(key)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            self._raise_schema_error(
                f"graph artifact {key} must be a list",
                path=path,
                details={"key": key, "actual_type": type(value).__name__},
            )
        return value

    def _require_mapping(
        self,
        value: Any,
        *,
        path: Path,
        key: str,
        index: int,
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            self._raise_schema_error(
                f"graph artifact {key} item must be an object",
                path=path,
                details={"key": key, "index": index, "actual_type": type(value).__name__},
            )
        return dict(value)

    def _validate_model(
        self,
        model_type: type[ModelT],
        payload: dict[str, Any],
        *,
        path: Path,
        key: str,
        index: int,
    ) -> ModelT:
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise ProjectUltApiError(
                "PROJECT_ULT_GRAPH_ARTIFACT_SCHEMA_INVALID",
                f"Invalid graph artifact {key} item: schema validation failed",
                status_code=500,
                details={
                    "path": str(path),
                    "key": key,
                    "index": index,
                    "errors": exc.errors(include_url=False),
                },
            ) from exc

    def _validate_token(self, value: str, field_name: str) -> str:
        if value and _SAFE_TOKEN_PATTERN.fullmatch(value):
            return value
        raise ProjectUltApiError(
            "PROJECT_ULT_GRAPH_QUERY_INVALID",
            f"{field_name} must be a non-empty graph-safe identifier",
            status_code=400,
            details={field_name: value},
        )

    def _validate_optional_token(self, value: str | None, field_name: str) -> str | None:
        if value in (None, ""):
            return None
        return self._validate_token(str(value), field_name)

    def _validate_channel(self, channel: str | None) -> str | None:
        if channel in (None, ""):
            return None
        if _CHANNEL_PATTERN.fullmatch(channel):
            return channel
        raise ProjectUltApiError(
            "PROJECT_ULT_GRAPH_QUERY_INVALID",
            "channel must be a valid graph channel identifier",
            status_code=400,
            details={"channel": channel},
        )

    def _raise_schema_error(
        self,
        message: str,
        *,
        path: Path,
        details: dict[str, Any] | None = None,
    ) -> None:
        raise ProjectUltApiError(
            "PROJECT_ULT_GRAPH_ARTIFACT_SCHEMA_INVALID",
            message,
            status_code=500,
            details={"path": str(path), **(details or {})},
        )

    def _artifact_source(self, kind: str, path: Path) -> SourceArtifact:
        return SourceArtifact(kind=kind, path=str(path), exists=True)

    def _unavailable_source(
        self,
        kind: str,
        path: Path,
        message: str,
    ) -> SourceArtifact:
        return SourceArtifact(
            kind=kind,
            path=str(path),
            exists=False,
            message=message,
        )
