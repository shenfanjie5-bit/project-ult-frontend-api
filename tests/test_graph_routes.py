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
    assert subgraph_payload["nodes"][0]["entity_role"] == "decision_target"
    assert {
        node["node_id"]: node["entity_role"] for node in subgraph_payload["nodes"]
    }["SECTOR_LIQUOR"] == "context_only"
    assert {
        edge["edge_id"] for edge in subgraph_payload["edges"]
    } == {
        "EDGE_600519_SECTOR_LIQUOR",
        "EDGE_600519_300750_MACRO_EVENT",
    }
    assert {
        edge["edge_id"]: edge["target_entity_role"]
        for edge in subgraph_payload["edges"]
    }["EDGE_600519_SECTOR_LIQUOR"] == "context_only"

    assert paths.status_code == 200
    paths_payload = paths.json()
    assert paths_payload["source_status"] == "available"
    assert paths_payload["query"]["channel"] == "event"
    assert paths_payload["total"] == 1
    assert paths_payload["paths"][0]["target"] == "ENT_STOCK_300750.SZ"
    assert paths_payload["paths"][0]["target_role"] == "decision_target"

    assert impact.status_code == 200
    impact_payload = impact.json()
    assert impact_payload["source_status"] == "available"
    assert impact_payload["query"] == {
        "entity_id": "ENT_STOCK_600519.SH",
        "cycle_id": None,
    }
    assert impact_payload["snapshot_id"] == "api3c_impact_001"
    assert impact_payload["total"] == 3
    assert impact_payload["items"] == impact_payload["impacted_entities"]
    assert impact_payload["items"][1]["entity_id"] == "ENT_STOCK_300750.SZ"
    assert impact_payload["items"][1]["entity_role"] == "decision_target"
    assert impact_payload["items"][2]["entity_id"] == "SECTOR_LIQUOR"
    assert impact_payload["items"][2]["entity_role"] == "context_only"


def test_graph_routes_enforce_mvp20_depth_cap(tmp_path: Path) -> None:
    _write_graph_artifacts(tmp_path)
    client = _client(tmp_path)

    subgraph = client.get(
        "/api/project-ult/graph/subgraph"
        "?seed=ENT_STOCK_600519.SH&depth=3"
    )
    paths = client.get(
        "/api/project-ult/graph/paths"
        "?seed=ENT_STOCK_600519.SH&depth=3"
    )

    assert subgraph.status_code == 422
    assert paths.status_code == 422


def test_ex3_signal_route_reads_sanitized_artifact(tmp_path: Path) -> None:
    _write_ex3_graph_signal_artifact(tmp_path)
    client = _client(tmp_path)

    response = client.get("/api/project-ult/graph/ex3-signals/CYCLE_20260416")

    assert response.status_code == 200
    assert response.json() == [
        {
            "cycle_id": "CYCLE_20260416",
            "candidate_id": 40,
            "delta_id": "delta-ex3-bridge",
            "delta_type": "edge_add",
            "selection_ref": "cycle_candidate_selection:CYCLE_20260416",
            "source_node": "ENT_STOCK_600519.SH",
            "target_node": "ENT_STOCK_000001.SZ",
            "relation_type": "supplier_of",
            "properties": {
                "impact_score": 0.91,
                "safe_details": {"direction": "positive"},
                "nested": {"safe": True},
                "safe_list": [{"flag": True}],
            },
            "evidence_refs": ["evidence-ex3-bridge"],
        }
    ]


def test_ex3_signal_schema_errors_do_not_leak_artifact_path(
    tmp_path: Path,
) -> None:
    _write_json(
        _ex3_graph_signal_artifact_root(tmp_path) / "CYCLE_20260416.json",
        {"cycle_id": "CYCLE_20260416", "signals": "bad"},
    )
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/graph/ex3-signals/CYCLE_20260416",
        headers={"x-request-id": "req_bad_ex3_schema"},
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "PROJECT_ULT_EX3_GRAPH_SIGNAL_SCHEMA_INVALID"
    assert error["request_id"] == "req_bad_ex3_schema"
    assert error["details"]["artifact"] == (
        "orchestrator/artifacts/frontend-api/ex3-graph-signals/"
        "CYCLE_20260416.json"
    )
    assert "path" not in error["details"]
    assert str(tmp_path) not in response.text


def test_ex3_signal_item_schema_errors_do_not_leak_artifact_path(
    tmp_path: Path,
) -> None:
    artifact_path = _ex3_graph_signal_artifact_root(tmp_path) / "CYCLE_20260416.json"
    _write_json(
        artifact_path,
        {"cycle_id": "CYCLE_20260416", "signals": ["not-object"]},
    )
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/graph/ex3-signals/CYCLE_20260416",
        headers={"x-request-id": "req_bad_ex3_signal_item"},
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "PROJECT_ULT_EX3_GRAPH_SIGNAL_SCHEMA_INVALID"
    assert error["request_id"] == "req_bad_ex3_signal_item"
    assert error["details"] == {
        "artifact": (
            "orchestrator/artifacts/frontend-api/ex3-graph-signals/"
            "CYCLE_20260416.json"
        ),
        "key": "signals",
        "index": 0,
        "actual_type": "str",
    }
    assert "path" not in error["details"]
    for leaked_token in (
        "/Users/",
        "/private/",
        "/var/",
        str(artifact_path),
        str(tmp_path),
    ):
        assert leaked_token not in response.text


def test_ex3_signal_source_errors_do_not_leak_artifact_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_path = _ex3_graph_signal_artifact_root(tmp_path) / "CYCLE_20260416.json"
    _write_json(artifact_path, {"cycle_id": "CYCLE_20260416", "signals": []})
    original_read_text = Path.read_text

    def raise_source_error(self: Path, *args, **kwargs) -> str:
        if self == artifact_path:
            raise OSError(f"permission denied: {artifact_path}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_source_error)
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/graph/ex3-signals/CYCLE_20260416",
        headers={"x-request-id": "req_bad_ex3_source"},
    )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "PROJECT_ULT_EX3_GRAPH_SIGNAL_SOURCE_UNAVAILABLE"
    assert error["request_id"] == "req_bad_ex3_source"
    assert error["details"] == {
        "artifact": (
            "orchestrator/artifacts/frontend-api/ex3-graph-signals/"
            "CYCLE_20260416.json"
        ),
        "error_type": "OSError",
    }
    assert str(tmp_path) not in response.text


def test_ex3_signal_route_drops_local_absolute_paths_from_public_fields(
    tmp_path: Path,
) -> None:
    _write_json(
        _ex3_graph_signal_artifact_root(tmp_path) / "CYCLE_20260416.json",
        {
            "cycle_id": "CYCLE_20260416",
            "signals": [
                {
                    "delta_id": "delta-ex3-bridge",
                    "delta_type": "edge_add",
                    "source_node": "ENT_STOCK_600519.SH",
                    "target_node": "ENT_STOCK_000001.SZ",
                    "relation_type": "supplier_of",
                    "properties": {
                        "normal_id": "evidence-ex3-bridge",
                        "docs_url": "https://example.test/evidence/ex3",
                        "artifact_location": "/var/tmp/ex3.txt",
                        "cache_location": "/private/var/tmp/ex3.json",
                        "file_uri": "file:///private/var/tmp/ex3.json",
                        "nested": {
                            "keep_id": "ENT_STOCK_600519.SH",
                            "local_path": "/Users/example/project/ex3.json",
                        },
                        "safe_list": [
                            "safe-ref",
                            "/var/tmp/list-entry.json",
                            "https://example.test/evidence/list-entry",
                        ],
                    },
                    "evidence_refs": [
                        "evidence-ex3-bridge",
                        "/var/tmp/evidence.json",
                        "/private/var/tmp/evidence.json",
                        "https://example.test/evidence/bridge",
                    ],
                    "cycle_id": "CYCLE_20260416",
                    "candidate_id": 40,
                    "selection_ref": "cycle_candidate_selection:CYCLE_20260416",
                }
            ],
        },
    )
    client = _client(tmp_path)

    response = client.get("/api/project-ult/graph/ex3-signals/CYCLE_20260416")

    assert response.status_code == 200
    signal = response.json()[0]
    assert signal["properties"] == {
        "normal_id": "evidence-ex3-bridge",
        "docs_url": "https://example.test/evidence/ex3",
        "nested": {"keep_id": "ENT_STOCK_600519.SH"},
        "safe_list": [
            "safe-ref",
            "https://example.test/evidence/list-entry",
        ],
    }
    assert signal["evidence_refs"] == [
        "evidence-ex3-bridge",
        "https://example.test/evidence/bridge",
    ]
    for leaked_value in (
        "/var/tmp/ex3.txt",
        "/private/var/tmp/ex3.json",
        "file:///private/var/tmp/ex3.json",
        "/Users/example/project/ex3.json",
        "/var/tmp/list-entry.json",
        "/var/tmp/evidence.json",
        "/private/var/tmp/evidence.json",
    ):
        assert leaked_value not in response.text


def test_ex3_signal_route_returns_404_without_path_leak_for_missing_artifact(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/graph/ex3-signals/CYCLE_20260416",
        headers={"x-request-id": "req_missing_ex3"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "PROJECT_ULT_EX3_GRAPH_SIGNAL_NOT_FOUND"
    assert payload["error"]["request_id"] == "req_missing_ex3"
    assert payload["error"]["details"] == {
        "artifact": (
            "orchestrator/artifacts/frontend-api/ex3-graph-signals/"
            "CYCLE_20260416.json"
        )
    }
    assert str(tmp_path) not in response.text


def test_ex3_signal_route_rejects_invalid_cycle_id(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/project-ult/graph/ex3-signals/bad..cycle")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PROJECT_ULT_GRAPH_QUERY_INVALID"


def test_ex3_signal_route_strips_forbidden_fields(tmp_path: Path) -> None:
    _write_ex3_graph_signal_artifact(tmp_path)
    client = _client(tmp_path)

    response = client.get("/api/project-ult/graph/ex3-signals/CYCLE_20260416")

    assert response.status_code == 200
    signal = response.json()[0]
    assert set(signal) == {
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
    forbidden_property_keys = {
        "chunk",
        "ingest_seq",
        "light_rag_artifact",
        "metadata",
        "payload_type",
        "private_id",
        "private_note",
        "provider",
        "queue_id",
        "raw_text",
        "secret",
        "source",
        "submitted_at",
        "traceback",
    }
    assert _collect_keys(signal["properties"]).isdisjoint(forbidden_property_keys)


def test_ex3_signal_route_is_get_only_and_no_raw_debug_route(tmp_path: Path) -> None:
    client = _client(tmp_path)

    ex3_methods = {
        method
        for route in client.app.routes
        if route.path == "/api/project-ult/graph/ex3-signals/{cycle_id}"
        for method in getattr(route, "methods", set())
    }
    route_paths = {route.path for route in client.app.routes}

    assert "GET" in ex3_methods
    assert ex3_methods.isdisjoint({"POST", "PUT", "PATCH", "DELETE"})
    assert "/api/project-ult/debug/graph/ex3-signals/{cycle_id}" not in route_paths
    assert "/api/project-ult/graph/ex3-signals/raw/{cycle_id}" not in route_paths


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
    assert any(
        node.get("entity_role") == "context_only"
        for node in subgraph_payload["nodes"]
    )

    assert paths.status_code == 200
    paths_payload = paths.json()
    assert paths_payload["source_status"] == "available"
    assert paths_payload["paths"][0]["seed"] == "ENT_STOCK_600519.SH"
    assert {
        path["target"]: path.get("target_role")
        for path in paths_payload["paths"]
    }["SECTOR_LIQUOR"] == "context_only"

    assert impact.status_code == 200
    impact_payload = impact.json()
    assert impact_payload["source_status"] == "available"
    assert impact_payload["snapshot_id"] == "api3c_impact_001"
    assert impact_payload["items"][1]["display_name"] == "CATL"
    assert any(
        item.get("entity_role") == "context_only"
        for item in impact_payload["items"]
    )


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
                    "entity_role": "decision_target",
                    "display_name": "Kweichow Moutai",
                    "properties": {"industry": "Liquor"},
                },
                {
                    "node_id": "ENT_STOCK_300750.SZ",
                    "label": "Entity",
                    "entity_id": "ENT_STOCK_300750.SZ",
                    "entity_role": "decision_target",
                    "display_name": "CATL",
                    "properties": {"industry": "Battery"},
                },
                {
                    "node_id": "SECTOR_LIQUOR",
                    "label": "Sector",
                    "entity_role": "context_only",
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
                    "source_entity_role": "decision_target",
                    "target_entity_role": "context_only",
                    "weight": 1.0,
                    "properties": {},
                },
                {
                    "edge_id": "EDGE_600519_300750_MACRO_EVENT",
                    "source_node_id": "ENT_STOCK_600519.SH",
                    "target_node_id": "ENT_STOCK_300750.SZ",
                    "relationship_type": "EVENT_IMPACT",
                    "channel": "event",
                    "source_entity_role": "decision_target",
                    "target_entity_role": "decision_target",
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
                    "target_role": "decision_target",
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
                    "target_role": "context_only",
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
                    "entity_role": "decision_target",
                    "display_name": "Kweichow Moutai",
                    "impact_score": 1.0,
                    "channels": ["fundamental"],
                    "drivers": ["seed_entity"],
                },
                {
                    "entity_id": "ENT_STOCK_300750.SZ",
                    "entity_role": "decision_target",
                    "display_name": "CATL",
                    "impact_score": 0.35,
                    "channels": ["event"],
                    "drivers": ["EDGE_600519_300750_MACRO_EVENT"],
                },
                {
                    "entity_id": "SECTOR_LIQUOR",
                    "entity_role": "context_only",
                    "display_name": "Liquor",
                    "impact_score": 0.12,
                    "channels": ["fundamental"],
                    "drivers": ["EDGE_600519_SECTOR_LIQUOR"],
                },
            ],
        },
    )


def _write_ex3_graph_signal_artifact(project_root: Path) -> None:
    _write_json(
        _ex3_graph_signal_artifact_root(project_root) / "CYCLE_20260416.json",
        {
            "cycle_id": "CYCLE_20260416",
            "signals": [
                {
                    "delta_id": "delta-ex3-bridge",
                    "delta_type": "edge_add",
                    "source_node": "ENT_STOCK_600519.SH",
                    "target_node": "ENT_STOCK_000001.SZ",
                    "relation_type": "supplier_of",
                    "properties": {
                        "impact_score": 0.91,
                        "safe_details": {
                            "direction": "positive",
                            "source": "drop",
                            "traceback": "drop",
                        },
                        "nested": {
                            "safe": True,
                            "private_note": "drop",
                        },
                        "safe_list": [
                            {
                                "flag": True,
                                "queue_id": "drop",
                            }
                        ],
                        "source": "drop",
                        "provider": "drop",
                        "raw_text": "drop",
                        "chunk": {"text": "drop"},
                        "light_rag_artifact": {"artifact_id": "drop"},
                        "metadata": {"source": "drop"},
                        "private_id": "drop",
                        "secret": "drop",
                        "submitted_at": "drop",
                        "traceback": "drop",
                        "large_blob": "x" * 4096,
                    },
                    "evidence_refs": ["evidence-ex3-bridge"],
                    "cycle_id": "CYCLE_20260416",
                    "candidate_id": 40,
                    "selection_ref": "cycle_candidate_selection:CYCLE_20260416",
                    "ingest_seq": 123,
                    "submitted_at": "drop",
                    "provider": "drop",
                    "source": "drop",
                    "private_id": "drop",
                    "queue_id": "drop",
                    "traceback": "drop",
                }
            ],
        },
    )


def _graph_artifact_root(project_root: Path) -> Path:
    return project_root / "graph-engine" / "artifacts" / "frontend-api"


def _ex3_graph_signal_artifact_root(project_root: Path) -> Path:
    return (
        project_root
        / "orchestrator"
        / "artifacts"
        / "frontend-api"
        / "ex3-graph-signals"
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _collect_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for item in value.values():
            keys.update(_collect_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_collect_keys(item))
        return keys
    return set()
