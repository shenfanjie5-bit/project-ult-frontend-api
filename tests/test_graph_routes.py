from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from frontend_api.app import create_app
from frontend_api.settings import FrontendApiSettings

PROJECT_ROOT = Path(
    os.getenv("PROJECT_ULT_TEST_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).resolve()


def test_graph_routes_read_artifacts(tmp_path: Path) -> None:
    _write_graph_artifacts(tmp_path)
    client = _client(tmp_path)

    subgraph = client.get(
        "/api/project-ult/graph/subgraph"
        "?seed=ENT_STOCK_600519.SH&depth=1&limit=50"
    )
    paths = client.get(
        "/api/project-ult/graph/paths"
        "?seed=ENT_STOCK_600519.SH&depth=2&limit=20&channel=event"
    )
    impact = client.get(
        "/api/project-ult/graph/impact?entity_id=ENT_STOCK_600519.SH"
    )

    assert subgraph.status_code == 200
    subgraph_payload = subgraph.json()
    assert subgraph_payload["source_status"] == "available"
    assert subgraph_payload["query"] == {
        "seed": "ENT_STOCK_600519.SH",
        "depth": 1,
        "limit": 50,
    }
    assert subgraph_payload["total_nodes"] == 3
    assert subgraph_payload["total_edges"] == 2
    assert subgraph_payload["truncated"] is False
    assert subgraph_payload["nodes"][0]["node_id"] == "ENT_STOCK_600519.SH"
    assert {
        edge["edge_id"] for edge in subgraph_payload["edges"]
    } == {
        "EDGE_600519_SECTOR_LIQUOR",
        "EDGE_600519_300750_MACRO_EVENT",
    }

    assert paths.status_code == 200
    paths_payload = paths.json()
    assert paths_payload["source_status"] == "available"
    assert paths_payload["query"]["channel"] == "event"
    assert paths_payload["total"] == 1
    assert paths_payload["paths"][0]["target"] == "ENT_STOCK_300750.SZ"

    assert impact.status_code == 200
    impact_payload = impact.json()
    assert impact_payload["source_status"] == "available"
    assert impact_payload["query"] == {
        "entity_id": "ENT_STOCK_600519.SH",
        "cycle_id": None,
    }
    assert impact_payload["snapshot_id"] == "api3c_impact_001"
    assert impact_payload["total"] == 2
    assert impact_payload["items"] == impact_payload["impacted_entities"]
    assert impact_payload["items"][1]["entity_id"] == "ENT_STOCK_300750.SZ"


def test_project_graph_artifacts_return_api3c_success_state() -> None:
    client = _client(PROJECT_ROOT)

    subgraph = client.get(
        "/api/project-ult/graph/subgraph"
        "?seed=ENT_STOCK_600519.SH&depth=1&limit=50"
    )
    paths = client.get(
        "/api/project-ult/graph/paths"
        "?seed=ENT_STOCK_600519.SH&depth=2&limit=20"
    )
    impact = client.get(
        "/api/project-ult/graph/impact?entity_id=ENT_STOCK_600519.SH"
    )

    assert subgraph.status_code == 200
    subgraph_payload = subgraph.json()
    assert subgraph_payload["source_status"] == "available"
    assert subgraph_payload["source"]["path"].endswith(
        "graph-engine/artifacts/frontend-api/subgraph.json"
    )
    assert subgraph_payload["total_nodes"] >= 3
    assert subgraph_payload["total_edges"] >= 2

    assert paths.status_code == 200
    paths_payload = paths.json()
    assert paths_payload["source_status"] == "available"
    assert paths_payload["paths"][0]["seed"] == "ENT_STOCK_600519.SH"

    assert impact.status_code == 200
    impact_payload = impact.json()
    assert impact_payload["source_status"] == "available"
    assert impact_payload["snapshot_id"] == "api3c_impact_001"
    assert impact_payload["items"][1]["display_name"] == "CATL"


def test_graph_routes_return_unavailable_without_sources(tmp_path: Path) -> None:
    client = _client(tmp_path)

    subgraph = client.get(
        "/api/project-ult/graph/subgraph?seed=ENT_STOCK_600519.SH"
    )
    paths = client.get("/api/project-ult/graph/paths?seed=ENT_STOCK_600519.SH")
    impact = client.get(
        "/api/project-ult/graph/impact?entity_id=ENT_STOCK_600519.SH"
    )

    assert subgraph.status_code == 200
    assert subgraph.json()["source_status"] == "unavailable"
    assert subgraph.json()["nodes"] == []
    assert subgraph.json()["edges"] == []
    assert paths.status_code == 200
    assert paths.json()["source_status"] == "unavailable"
    assert paths.json()["paths"] == []
    assert impact.status_code == 200
    assert impact.json()["source_status"] == "unavailable"
    assert impact.json()["items"] == []


def test_graph_schema_drift_uses_error_envelope(tmp_path: Path) -> None:
    _write_json(_graph_artifact_root(tmp_path) / "subgraph.json", {"nodes": "bad"})
    _write_json(_graph_artifact_root(tmp_path) / "paths.json", {"paths": [{}]})
    client = _client(tmp_path)

    subgraph = client.get(
        "/api/project-ult/graph/subgraph?seed=ENT_STOCK_600519.SH",
        headers={"x-request-id": "req_bad_subgraph"},
    )
    paths = client.get(
        "/api/project-ult/graph/paths?seed=ENT_STOCK_600519.SH",
        headers={"x-request-id": "req_bad_paths"},
    )

    assert subgraph.status_code == 500
    assert subgraph.json()["error"]["code"] == (
        "PROJECT_ULT_GRAPH_ARTIFACT_SCHEMA_INVALID"
    )
    assert subgraph.json()["error"]["request_id"] == "req_bad_subgraph"
    assert paths.status_code == 500
    assert paths.json()["error"]["code"] == (
        "PROJECT_ULT_GRAPH_ARTIFACT_SCHEMA_INVALID"
    )
    assert paths.json()["error"]["request_id"] == "req_bad_paths"


def test_graph_routes_reject_invalid_query(tmp_path: Path) -> None:
    client = _client(tmp_path)

    seed_response = client.get("/api/project-ult/graph/subgraph?seed=../secret")
    channel_response = client.get(
        "/api/project-ult/graph/paths"
        "?seed=ENT_STOCK_600519.SH&channel=../secret"
    )

    assert seed_response.status_code == 400
    assert seed_response.json()["error"]["code"] == "PROJECT_ULT_GRAPH_QUERY_INVALID"
    assert channel_response.status_code == 400
    assert channel_response.json()["error"]["code"] == (
        "PROJECT_ULT_GRAPH_QUERY_INVALID"
    )


def test_api3c_does_not_register_project_ult_post_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)

    project_ult_post_routes = sorted(
        route.path
        for route in client.app.routes
        if "POST" in getattr(route, "methods", set())
        and route.path.startswith("/api/project-ult")
    )

    assert project_ult_post_routes == []


def _client(project_root: Path) -> TestClient:
    app = create_app(
        FrontendApiSettings(
            project_root=project_root,
            profile="lite-local",
            mode="lite-local",
        )
    )
    return TestClient(app)


def _write_graph_artifacts(project_root: Path) -> None:
    root = _graph_artifact_root(project_root)
    _write_json(
        root / "subgraph.json",
        {
            "nodes": [
                {
                    "node_id": "ENT_STOCK_600519.SH",
                    "label": "Entity",
                    "entity_id": "ENT_STOCK_600519.SH",
                    "display_name": "Kweichow Moutai",
                    "properties": {"industry": "Liquor"},
                },
                {
                    "node_id": "ENT_STOCK_300750.SZ",
                    "label": "Entity",
                    "entity_id": "ENT_STOCK_300750.SZ",
                    "display_name": "CATL",
                    "properties": {"industry": "Battery"},
                },
                {
                    "node_id": "SECTOR_LIQUOR",
                    "label": "Sector",
                    "display_name": "Liquor",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "edge_id": "EDGE_600519_SECTOR_LIQUOR",
                    "source_node_id": "ENT_STOCK_600519.SH",
                    "target_node_id": "SECTOR_LIQUOR",
                    "relationship_type": "SECTOR_MEMBERSHIP",
                    "channel": "fundamental",
                    "weight": 1.0,
                    "properties": {},
                },
                {
                    "edge_id": "EDGE_600519_300750_MACRO_EVENT",
                    "source_node_id": "ENT_STOCK_600519.SH",
                    "target_node_id": "ENT_STOCK_300750.SZ",
                    "relationship_type": "EVENT_IMPACT",
                    "channel": "event",
                    "weight": 0.35,
                    "properties": {},
                },
            ],
        },
    )
    _write_json(
        root / "paths.json",
        {
            "paths": [
                {
                    "path_id": "PATH_600519_TO_300750_EVENT",
                    "seed": "ENT_STOCK_600519.SH",
                    "target": "ENT_STOCK_300750.SZ",
                    "nodes": ["ENT_STOCK_600519.SH", "ENT_STOCK_300750.SZ"],
                    "edges": ["EDGE_600519_300750_MACRO_EVENT"],
                    "depth": 1,
                    "channel": "event",
                    "score": 0.35,
                    "summary": "Macro event channel connects the two entities.",
                },
                {
                    "path_id": "PATH_600519_TO_SECTOR_LIQUOR",
                    "seed": "ENT_STOCK_600519.SH",
                    "target": "SECTOR_LIQUOR",
                    "nodes": ["ENT_STOCK_600519.SH", "SECTOR_LIQUOR"],
                    "edges": ["EDGE_600519_SECTOR_LIQUOR"],
                    "depth": 1,
                    "channel": "fundamental",
                    "score": 1.0,
                    "summary": "Sector membership path.",
                },
            ]
        },
    )
    _write_json(
        root / "impact.json",
        {
            "entity_id": "ENT_STOCK_600519.SH",
            "cycle_id": "CYCLE_20260424",
            "snapshot_id": "api3c_impact_001",
            "items": [
                {
                    "entity_id": "ENT_STOCK_600519.SH",
                    "display_name": "Kweichow Moutai",
                    "impact_score": 1.0,
                    "channels": ["fundamental"],
                    "drivers": ["seed_entity"],
                },
                {
                    "entity_id": "ENT_STOCK_300750.SZ",
                    "display_name": "CATL",
                    "impact_score": 0.35,
                    "channels": ["event"],
                    "drivers": ["EDGE_600519_300750_MACRO_EVENT"],
                },
            ],
        },
    )


def _graph_artifact_root(project_root: Path) -> Path:
    return project_root / "graph-engine" / "artifacts" / "frontend-api"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
