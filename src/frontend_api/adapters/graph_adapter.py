"""Read-only adapter for graph-engine frontend-api artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from math import isfinite
from pathlib import Path
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import SourceArtifact
from frontend_api.schemas.graph import (
    Ex3GraphSignal,
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
_EX3_GRAPH_SIGNAL_ARTIFACT_ROOT = (
    "orchestrator",
    "artifacts",
    "frontend-api",
    "ex3-graph-signals",
)
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_CHANNEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_EX3_SIGNAL_KEYS = frozenset(
    {
        "cycle_id",
        "candidate_id",
        "delta_id",
        "delta_type",
        "selection_ref",
        "source_node",
        "target_node",
        "relation_type",
        "properties",
        "evidence_refs",
    }
)
_EX3_SIGNAL_COLLECTION_KEYS = (
    "signals",
    "items",
    "ex3_graph_signals",
    "same_cycle_ex3_graph_signals",
)
_UNSAFE_EX3_PROPERTY_KEYS = frozenset(
    {
        "chunk",
        "ingest_seq",
        "light_rag_artifact",
        "metadata",
        "payload_type",
        "raw_text",
        "rejection_reason",
        "submitted_at",
        "submitted_by",
        "validation_status",
    }
)
_UNSAFE_EX3_PROPERTY_KEY_MARKERS = (
    "blob",
    "chunk",
    "light_rag",
    "lightrag",
    "log",
    "metadata",
    "private",
    "provider",
    "queue",
    "raw",
    "secret",
    "source",
    "traceback",
)
_MAX_EX3_SIGNAL_STRING_LENGTH = 2048
_MAX_EX3_SIGNAL_COLLECTION_ITEMS = 50
_MAX_EX3_SIGNAL_DEPTH = 4
_DROP_EX3_SIGNAL_VALUE = object()


class GraphReadAdapter:
    """Read graph-engine frontend-api artifacts without importing graph-engine."""

    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.artifact_root = self.project_root.joinpath(*_GRAPH_ARTIFACT_ROOT)
        self.ex3_signal_artifact_root = self.project_root.joinpath(
            *_EX3_GRAPH_SIGNAL_ARTIFACT_ROOT
        )

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

    def get_ex3_signals(self, *, cycle_id: str) -> list[Ex3GraphSignal]:
        validated_cycle_id = self._validate_artifact_cycle_id(cycle_id)
        path = self.ex3_signal_artifact_root / f"{validated_cycle_id}.json"
        if not path.exists():
            raise ProjectUltApiError(
                "PROJECT_ULT_EX3_GRAPH_SIGNAL_NOT_FOUND",
                "Ex-3 graph signal artifact not found",
                status_code=404,
                details={"artifact": self._ex3_signal_artifact_key(validated_cycle_id)},
            )

        raw = self._load_json_value(
            path,
            source_unavailable_code="PROJECT_ULT_EX3_GRAPH_SIGNAL_SOURCE_UNAVAILABLE",
            schema_invalid_code="PROJECT_ULT_EX3_GRAPH_SIGNAL_SCHEMA_INVALID",
        )
        raw_items = self._ex3_signal_items(
            raw,
            cycle_id=validated_cycle_id,
            path=path,
        )
        return [
            self._sanitize_ex3_signal(
                self._require_mapping(item, path=path, key="signals", index=index),
                cycle_id=validated_cycle_id,
                path=path,
                index=index,
            )
            for index, item in enumerate(raw_items)
        ]

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

    def _ex3_signal_items(
        self,
        raw: Any,
        *,
        cycle_id: str,
        path: Path,
    ) -> Sequence[Any]:
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            return raw
        if not isinstance(raw, Mapping):
            self._raise_ex3_schema_error(
                "Ex-3 graph signal artifact root must be an object or list",
                path=path,
                details={"actual_type": type(raw).__name__},
            )

        artifact_cycle_id = raw.get("cycle_id")
        if artifact_cycle_id is not None and artifact_cycle_id != cycle_id:
            self._raise_ex3_schema_error(
                "Ex-3 graph signal artifact cycle_id does not match request",
                path=path,
                details={"cycle_id": artifact_cycle_id, "requested_cycle_id": cycle_id},
            )

        for key in _EX3_SIGNAL_COLLECTION_KEYS:
            value = raw.get(key)
            if value is None:
                continue
            if not isinstance(value, Sequence) or isinstance(
                value, (str, bytes, bytearray)
            ):
                self._raise_ex3_schema_error(
                    f"Ex-3 graph signal artifact {key} must be a list",
                    path=path,
                    details={"key": key, "actual_type": type(value).__name__},
                )
            return value

        if _EX3_SIGNAL_KEYS.intersection(raw.keys()):
            return (raw,)

        self._raise_ex3_schema_error(
            "Ex-3 graph signal artifact must contain a signal list",
            path=path,
            details={"expected_keys": list(_EX3_SIGNAL_COLLECTION_KEYS)},
        )

    def _sanitize_ex3_signal(
        self,
        raw: Mapping[str, Any],
        *,
        cycle_id: str,
        path: Path,
        index: int,
    ) -> Ex3GraphSignal:
        raw_cycle_id = raw.get("cycle_id", cycle_id)
        if raw_cycle_id != cycle_id:
            self._raise_ex3_schema_error(
                "Ex-3 graph signal cycle_id does not match request",
                path=path,
                details={"index": index, "cycle_id": raw_cycle_id},
            )

        raw_properties = raw.get("properties", {})
        if raw_properties is None:
            raw_properties = {}
        if not isinstance(raw_properties, Mapping):
            self._raise_ex3_schema_error(
                "Ex-3 graph signal properties must be an object",
                path=path,
                details={
                    "index": index,
                    "actual_type": type(raw_properties).__name__,
                },
            )

        payload = {
            "cycle_id": cycle_id,
            "candidate_id": self._ex3_candidate_id(raw.get("candidate_id"), path, index),
            "delta_id": self._required_ex3_text(raw, "delta_id", path, index),
            "delta_type": self._required_ex3_text(raw, "delta_type", path, index),
            "selection_ref": self._required_ex3_text(
                raw,
                "selection_ref",
                path,
                index,
            ),
            "source_node": self._required_ex3_text(raw, "source_node", path, index),
            "target_node": self._required_ex3_text(raw, "target_node", path, index),
            "relation_type": self._required_ex3_text(raw, "relation_type", path, index),
            "properties": self._sanitize_ex3_properties(raw_properties),
            "evidence_refs": self._ex3_evidence_refs(raw, path, index),
        }
        return self._validate_model(
            Ex3GraphSignal,
            payload,
            path=path,
            key="signals",
            index=index,
        )

    def _required_ex3_text(
        self,
        raw: Mapping[str, Any],
        key: str,
        path: Path,
        index: int,
    ) -> str:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        self._raise_ex3_schema_error(
            f"Ex-3 graph signal {key} must be a non-empty string",
            path=path,
            details={"index": index, "key": key, "actual_type": type(value).__name__},
        )

    def _ex3_candidate_id(self, value: Any, path: Path, index: int) -> int:
        if isinstance(value, bool):
            pass
        elif isinstance(value, int):
            return value
        elif isinstance(value, str) and value.isdecimal():
            return int(value)
        self._raise_ex3_schema_error(
            "Ex-3 graph signal candidate_id must be an integer",
            path=path,
            details={"index": index, "actual_type": type(value).__name__},
        )

    def _ex3_evidence_refs(
        self,
        raw: Mapping[str, Any],
        path: Path,
        index: int,
    ) -> list[str]:
        value = raw.get("evidence_refs", raw.get("evidence", []))
        if value is None:
            return []
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            self._raise_ex3_schema_error(
                "Ex-3 graph signal evidence_refs must be a list",
                path=path,
                details={"index": index, "actual_type": type(value).__name__},
            )

        refs: list[str] = []
        for ref_index, ref in enumerate(value):
            if ref_index >= _MAX_EX3_SIGNAL_COLLECTION_ITEMS:
                break
            if not isinstance(ref, str) or not ref.strip():
                self._raise_ex3_schema_error(
                    "Ex-3 graph signal evidence_refs items must be non-empty strings",
                    path=path,
                    details={
                        "index": index,
                        "ref_index": ref_index,
                        "actual_type": type(ref).__name__,
                    },
                )
            if len(ref) <= _MAX_EX3_SIGNAL_STRING_LENGTH:
                refs.append(ref.strip())
        return refs

    def _sanitize_ex3_properties(
        self,
        properties: Mapping[str, Any],
    ) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in properties.items():
            if self._unsafe_ex3_property_key(key):
                continue
            safe_value = self._safe_ex3_value(value, depth=0)
            if safe_value is not _DROP_EX3_SIGNAL_VALUE:
                sanitized[str(key)] = safe_value
        return sanitized

    def _safe_ex3_value(self, value: Any, *, depth: int) -> Any:
        if depth > _MAX_EX3_SIGNAL_DEPTH:
            return _DROP_EX3_SIGNAL_VALUE
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value if isfinite(value) else _DROP_EX3_SIGNAL_VALUE
        if isinstance(value, str):
            if len(value) > _MAX_EX3_SIGNAL_STRING_LENGTH:
                return _DROP_EX3_SIGNAL_VALUE
            return value
        if isinstance(value, Mapping):
            safe_mapping: dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= _MAX_EX3_SIGNAL_COLLECTION_ITEMS:
                    break
                if self._unsafe_ex3_property_key(key):
                    continue
                safe_item = self._safe_ex3_value(item, depth=depth + 1)
                if safe_item is not _DROP_EX3_SIGNAL_VALUE:
                    safe_mapping[str(key)] = safe_item
            return safe_mapping
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            safe_items: list[Any] = []
            for index, item in enumerate(value):
                if index >= _MAX_EX3_SIGNAL_COLLECTION_ITEMS:
                    break
                safe_item = self._safe_ex3_value(item, depth=depth + 1)
                if safe_item is not _DROP_EX3_SIGNAL_VALUE:
                    safe_items.append(safe_item)
            return safe_items
        return _DROP_EX3_SIGNAL_VALUE

    def _unsafe_ex3_property_key(self, key: object) -> bool:
        if not isinstance(key, str):
            return True
        normalized = key.strip().lower()
        if not normalized or normalized.startswith("_"):
            return True
        if normalized in _UNSAFE_EX3_PROPERTY_KEYS:
            return True
        key_tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
        if "log" in key_tokens:
            return True
        return any(
            marker in normalized
            for marker in _UNSAFE_EX3_PROPERTY_KEY_MARKERS
            if marker != "log"
        )

    def _load_json_value(
        self,
        path: Path,
        *,
        source_unavailable_code: str,
        schema_invalid_code: str,
    ) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectUltApiError(
                schema_invalid_code,
                "Invalid JSON artifact",
                status_code=500,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise ProjectUltApiError(
                source_unavailable_code,
                "Cannot read graph artifact",
                status_code=503,
                details={"path": str(path), "error": str(exc)},
            ) from exc

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

    def _validate_artifact_cycle_id(self, value: str) -> str:
        if (
            value
            and len(value) <= 128
            and _SAFE_TOKEN_PATTERN.fullmatch(value)
            and ".." not in value
            and not value.startswith(".")
        ):
            return value
        raise ProjectUltApiError(
            "PROJECT_ULT_GRAPH_QUERY_INVALID",
            "cycle_id must be a non-empty graph-safe artifact identifier",
            status_code=400,
            details={"cycle_id": value},
        )

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

    def _raise_ex3_schema_error(
        self,
        message: str,
        *,
        path: Path,
        details: dict[str, Any] | None = None,
    ) -> None:
        raise ProjectUltApiError(
            "PROJECT_ULT_EX3_GRAPH_SIGNAL_SCHEMA_INVALID",
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

    def _ex3_signal_artifact_key(self, cycle_id: str) -> str:
        return "/".join((*_EX3_GRAPH_SIGNAL_ARTIFACT_ROOT, f"{cycle_id}.json"))
