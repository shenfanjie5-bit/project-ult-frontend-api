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


def test_cycle_formal_routes_read_artifacts(tmp_path: Path) -> None:
    root = _artifact_root(tmp_path)
    _write_json(
        root / "cycles.json",
        {
            "items": [
                {
                    "cycle_id": "CYCLE_20260424",
                    "status": "published",
                    "cycle_date": "2026-04-24",
                }
            ]
        },
    )
    _write_json(
        root / "cycles" / "CYCLE_20260424.json",
        {"cycle_id": "CYCLE_20260424", "status": "published"},
    )
    _write_json(
        root / "formal" / "world_state_snapshot" / "latest.json",
        {
            "object_type": "world_state_snapshot",
            "cycle_id": "CYCLE_20260424",
            "payload": {"regime": "risk_on", "entities": []},
        },
    )
    _write_json(
        root / "formal" / "world_state_snapshot" / "CYCLE_20260424.json",
        {
            "object_type": "world_state_snapshot",
            "cycle_id": "CYCLE_20260424",
            "payload": {"entities": [{"entity_id": "ENT_STOCK_000001.SZ"}]},
        },
    )
    _write_json(
        root / "formal" / "official_alpha_pool" / "latest.json",
        {
            "object_type": "official_alpha_pool",
            "cycle_id": "CYCLE_20260424",
            "payload": {"selected_entities": []},
        },
    )
    _write_json(
        root / "formal" / "recommendation_snapshot" / "latest.json",
        {
            "object_type": "recommendation_snapshot",
            "cycle_id": "CYCLE_20260424",
            "payload": {"recommendations": [{"entity_id": "ENT_STOCK_000001.SZ"}]},
        },
    )
    _write_json(
        root / "manifests" / "latest.json",
        {
            "published_cycle_id": "CYCLE_20260424",
            "formal_table_snapshots": {
                "formal.world_state_snapshot": {"snapshot_id": 123}
            },
        },
    )
    client = _client(tmp_path)

    cycles = client.get("/api/project-ult/cycles")
    cycle = client.get("/api/project-ult/cycles/CYCLE_20260424")
    formal_latest = client.get("/api/project-ult/formal/world_state_snapshot")
    formal_cycle = client.get(
        "/api/project-ult/formal/world_state_snapshot/CYCLE_20260424"
    )
    manifest = client.get("/api/project-ult/manifests/latest")
    legacy_world_state = client.get("/api/world-state/latest")
    legacy_pool = client.get("/api/pool/latest")
    legacy_recommendations = client.get("/api/recommendations/latest")

    assert cycles.status_code == 200
    assert cycles.json()["total"] == 1
    assert cycle.status_code == 200
    assert cycle.json()["status"] == "published"
    assert formal_latest.status_code == 200
    assert formal_latest.json()["object_type"] == "world_state_snapshot"
    assert formal_cycle.status_code == 200
    assert formal_cycle.json()["payload"]["entities"][0]["entity_id"] == (
        "ENT_STOCK_000001.SZ"
    )
    assert manifest.status_code == 200
    assert manifest.json()["cycle_id"] == "CYCLE_20260424"
    assert legacy_world_state.status_code == 200
    assert legacy_world_state.json()["regime"] == "risk_on"
    assert "payload" not in legacy_world_state.json()
    assert legacy_pool.status_code == 200
    assert legacy_pool.json()["selected_entities"] == []
    assert "object_type" not in legacy_pool.json()
    assert legacy_recommendations.status_code == 200
    assert legacy_recommendations.json()["recommendations"][0]["entity_id"] == (
        "ENT_STOCK_000001.SZ"
    )
    assert "payload" not in legacy_recommendations.json()


def test_project_artifacts_return_api2b_success_state() -> None:
    client = _client(PROJECT_ROOT)

    cycles = client.get("/api/project-ult/cycles")
    manifest = client.get("/api/project-ult/manifests/latest")
    formal_world_state = client.get("/api/project-ult/formal/world_state_snapshot")
    formal_pool = client.get("/api/project-ult/formal/official_alpha_pool")
    formal_recommendations = client.get(
        "/api/project-ult/formal/recommendation_snapshot"
    )
    legacy_world_state = client.get("/api/world-state/latest")
    legacy_pool = client.get("/api/pool/latest")
    legacy_recommendations = client.get("/api/recommendations/latest")

    assert cycles.status_code == 200
    cycles_payload = cycles.json()
    assert cycles_payload["source_status"] == "available"
    assert cycles_payload["source"]["kind"] == "cycle_index"
    assert cycles_payload["source"]["path"].endswith(
        "data-platform/artifacts/frontend-api/cycles.json"
    )
    assert cycles_payload["total"] >= 1
    assert cycles_payload["items"][0]["cycle_id"] == "CYCLE_20260424"

    assert manifest.status_code == 200
    manifest_payload = manifest.json()
    assert manifest_payload["source_status"] == "available"
    snapshots = manifest_payload["formal_table_snapshots"]
    assert isinstance(snapshots, dict)
    assert snapshots.keys() >= {
        "world_state_snapshot",
        "official_alpha_pool",
        "recommendation_snapshot",
    }
    assert all(isinstance(snapshot, dict) for snapshot in snapshots.values())
    assert snapshots["world_state_snapshot"]["snapshot_id"] == "api2b_world_state_001"

    assert formal_world_state.status_code == 200
    world_state_payload = formal_world_state.json()
    assert world_state_payload["object_type"] == "world_state_snapshot"
    assert world_state_payload["source_status"] == "available"
    assert world_state_payload["source"]["kind"] == "formal_object"
    assert world_state_payload["payload"]["regime"] == "range_bound"

    assert formal_pool.status_code == 200
    assert formal_pool.json()["payload"]["core_pool"][0]["stock_id"] == "600519.SH"
    assert formal_recommendations.status_code == 200
    assert formal_recommendations.json()["payload"]["recommendations"][0]["rank"] == 1

    assert legacy_world_state.status_code == 200
    assert legacy_world_state.json()["regime"] == "range_bound"
    assert "payload" not in legacy_world_state.json()
    assert "source_status" not in legacy_world_state.json()
    assert legacy_pool.status_code == 200
    assert legacy_pool.json()["core_pool"][0]["stock_id"] == "600519.SH"
    assert "object_type" not in legacy_pool.json()
    assert legacy_recommendations.status_code == 200
    assert legacy_recommendations.json()["recommendations"][0]["rank"] == 1
    assert "payload" not in legacy_recommendations.json()


def test_cycle_routes_return_error_envelope_when_formal_source_missing(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/formal/world_state_snapshot",
        headers={"x-request-id": "req_formal_missing"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "PROJECT_ULT_FORMAL_SOURCE_UNAVAILABLE"
    assert payload["error"]["request_id"] == "req_formal_missing"
    assert payload["error"]["details"]["artifact_path"].endswith(
        "formal/world_state_snapshot/latest.json"
    )


def test_cycle_routes_reject_invalid_identifiers_with_error_envelope(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    cycle_response = client.get("/api/project-ult/cycles/not-a-cycle")
    formal_response = client.get("/api/project-ult/formal/not-valid")

    assert cycle_response.status_code == 400
    assert cycle_response.json()["error"]["code"] == "PROJECT_ULT_CYCLE_ID_INVALID"
    assert formal_response.status_code == 400
    assert formal_response.json()["error"]["code"] == (
        "PROJECT_ULT_FORMAL_OBJECT_TYPE_INVALID"
    )


def test_api2a_does_not_register_command_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    route_methods = {
        (route.path, method)
        for route in client.app.routes
        for method in getattr(route, "methods", set())
    }

    forbidden_posts = {
        "/api/project-ult/cycles",
        "/api/project-ult/cycles/{cycle_id}/freeze",
        "/api/project-ult/cycles/{cycle_id}/transition",
        "/api/project-ult/compat/run",
        "/api/project-ult/smoke/{module_id}",
    }
    for path in forbidden_posts:
        assert (path, "POST") not in route_methods
    assert all(
        method != "POST" or not path.startswith("/api/project-ult")
        for path, method in route_methods
    )


def _client(project_root: Path) -> TestClient:
    app = create_app(
        FrontendApiSettings(
            project_root=project_root,
            profile="lite-local",
            mode="lite-local",
        )
    )
    return TestClient(app)


def _artifact_root(project_root: Path) -> Path:
    return project_root / "data-platform" / "artifacts" / "frontend-api"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
