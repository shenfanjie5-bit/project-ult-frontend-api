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


def test_entity_data_routes_read_artifacts(tmp_path: Path) -> None:
    _write_entity_index(tmp_path)
    _write_data_artifact(
        tmp_path,
        namespace="canonical",
        name="stock_basic",
        columns=["ts_code", "name", "industry"],
        items=[
            {"ts_code": "600519.SH", "name": "Kweichow Moutai", "industry": "Liquor"},
            {"ts_code": "300750.SZ", "name": "CATL", "industry": "Battery"},
        ],
    )
    _write_data_artifact(
        tmp_path,
        namespace="raw",
        name="tushare_stock_basic",
        columns=["source", "ts_code", "name"],
        items=[
            {"source": "tushare", "ts_code": "600519.SH", "name": "Kweichow Moutai"},
            {"source": "tushare", "ts_code": "300750.SZ", "name": "CATL"},
        ],
    )
    client = _client(tmp_path)

    search = client.get("/api/project-ult/entities/search?q=moutai&limit=1")
    profile = client.get("/api/project-ult/entities/ENT_STOCK_600519.SH")
    canonical = client.get("/api/project-ult/data/canonical/stock_basic?limit=1")
    raw = client.get("/api/project-ult/data/raw/tushare_stock_basic?limit=1&cursor=1")

    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["source_status"] == "available"
    assert search_payload["source"]["kind"] == "entity_index"
    assert search_payload["total"] == 1
    assert search_payload["next_cursor"] is None
    assert search_payload["items"][0]["entity_id"] == "ENT_STOCK_600519.SH"

    assert profile.status_code == 200
    profile_payload = profile.json()
    assert profile_payload["source_status"] == "available"
    assert profile_payload["entity_id"] == "ENT_STOCK_600519.SH"
    assert profile_payload["profile"]["canonical_entity"]["display_name"] == (
        "Kweichow Moutai"
    )

    assert canonical.status_code == 200
    canonical_payload = canonical.json()
    assert canonical_payload["source_status"] == "available"
    assert canonical_payload["table"] == "stock_basic"
    assert canonical_payload["columns"] == ["ts_code", "name", "industry"]
    assert canonical_payload["total"] == 2
    assert canonical_payload["next_cursor"] == "1"
    assert canonical_payload["items"][0]["ts_code"] == "600519.SH"

    assert raw.status_code == 200
    raw_payload = raw.json()
    assert raw_payload["source_status"] == "available"
    assert raw_payload["source_name"] == "tushare_stock_basic"
    assert raw_payload["total"] == 2
    assert raw_payload["next_cursor"] is None
    assert raw_payload["items"][0]["ts_code"] == "300750.SZ"


def test_entity_search_route_uses_cursor_for_next_page(tmp_path: Path) -> None:
    _write_entity_index(tmp_path)
    client = _client(tmp_path)

    page1 = client.get("/api/project-ult/entities/search?limit=1")
    page2 = client.get("/api/project-ult/entities/search?limit=1&cursor=1")

    assert page1.status_code == 200
    assert page1.json()["items"][0]["entity_id"] == "ENT_STOCK_600519.SH"
    assert page1.json()["next_cursor"] == "1"
    assert page2.status_code == 200
    assert page2.json()["items"][0]["entity_id"] == "ENT_STOCK_300750.SZ"
    assert page2.json()["next_cursor"] is None


def test_project_artifacts_return_api3a_success_state() -> None:
    client = _client(PROJECT_ROOT)

    search = client.get("/api/project-ult/entities/search?q=600519&limit=5")
    profile = client.get("/api/project-ult/entities/ENT_STOCK_600519.SH")
    canonical = client.get("/api/project-ult/data/canonical/stock_basic?limit=1")
    raw = client.get("/api/project-ult/data/raw/tushare_stock_basic?limit=1")

    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["source_status"] == "available"
    assert search_payload["source"]["path"].endswith(
        "entity-registry/artifacts/frontend-api/entities.json"
    )
    assert search_payload["items"][0]["entity_id"] == "ENT_STOCK_600519.SH"

    assert profile.status_code == 200
    profile_payload = profile.json()
    assert profile_payload["source_status"] == "available"
    assert profile_payload["profile"]["canonical_entity"]["canonical_entity_id"] == (
        "ENT_STOCK_600519.SH"
    )

    assert canonical.status_code == 200
    canonical_payload = canonical.json()
    assert canonical_payload["source_status"] == "available"
    assert canonical_payload["source"]["path"].endswith(
        "data-platform/artifacts/frontend-api/data/canonical/stock_basic.json"
    )
    assert canonical_payload["columns"] == [
        "ts_code",
        "symbol",
        "name",
        "area",
        "industry",
        "list_status",
    ]
    assert canonical_payload["items"][0]["ts_code"] == "600519.SH"

    assert raw.status_code == 200
    raw_payload = raw.json()
    assert raw_payload["source_status"] == "available"
    assert raw_payload["source"]["path"].endswith(
        "data-platform/artifacts/frontend-api/data/raw/tushare_stock_basic.json"
    )
    assert raw_payload["items"][0]["source"] == "tushare"


def test_entity_data_routes_return_unavailable_without_sources(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    search = client.get("/api/project-ult/entities/search?q=missing")
    profile = client.get(
        "/api/project-ult/entities/ENT_STOCK_600519.SH",
        headers={"x-request-id": "req_entity_source_missing"},
    )
    canonical = client.get("/api/project-ult/data/canonical/stock_basic")
    raw = client.get("/api/project-ult/data/raw/tushare_stock_basic")

    assert search.status_code == 200
    assert search.json()["source_status"] == "unavailable"
    assert search.json()["items"] == []
    assert search.json()["total"] == 0
    assert profile.status_code == 503
    assert profile.json()["error"]["code"] == "PROJECT_ULT_ENTITY_SOURCE_UNAVAILABLE"
    assert profile.json()["error"]["request_id"] == "req_entity_source_missing"
    assert canonical.status_code == 200
    assert canonical.json()["source_status"] == "unavailable"
    assert canonical.json()["items"] == []
    assert raw.status_code == 200
    assert raw.json()["source_status"] == "unavailable"
    assert raw.json()["items"] == []


def test_entity_not_found_is_distinct_from_source_unavailable(
    tmp_path: Path,
) -> None:
    _write_entity_index(tmp_path)
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/entities/ENT_STOCK_UNKNOWN",
        headers={"x-request-id": "req_entity_not_found"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "PROJECT_ULT_ENTITY_NOT_FOUND"
    assert payload["error"]["request_id"] == "req_entity_not_found"


def test_entity_data_schema_drift_uses_error_envelope(tmp_path: Path) -> None:
    _write_json(_entity_artifact_root(tmp_path) / "entities.json", {"items": [{}]})
    _write_json(
        _data_artifact_root(tmp_path) / "canonical" / "stock_basic.json",
        {"items": "not-a-list"},
    )
    client = _client(tmp_path)

    entity_response = client.get(
        "/api/project-ult/entities/search",
        headers={"x-request-id": "req_bad_entity_artifact"},
    )
    data_response = client.get(
        "/api/project-ult/data/canonical/stock_basic",
        headers={"x-request-id": "req_bad_data_artifact"},
    )

    assert entity_response.status_code == 500
    assert entity_response.json()["error"]["code"] == (
        "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID"
    )
    assert entity_response.json()["error"]["request_id"] == "req_bad_entity_artifact"
    assert data_response.status_code == 500
    assert data_response.json()["error"]["code"] == (
        "PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID"
    )
    assert data_response.json()["error"]["request_id"] == "req_bad_data_artifact"


def test_entity_data_routes_reject_unsafe_identifiers(tmp_path: Path) -> None:
    client = _client(tmp_path)

    entity_response = client.get("/api/project-ult/entities/../secret")
    data_response = client.get("/api/project-ult/data/canonical/../secret")
    cursor_response = client.get(
        "/api/project-ult/data/raw/tushare_stock_basic?cursor=not-an-offset"
    )

    assert entity_response.status_code == 404
    assert data_response.status_code == 404
    assert cursor_response.status_code == 400
    assert cursor_response.json()["error"]["code"] == "PROJECT_ULT_CURSOR_INVALID"


def test_api3a_does_not_register_project_ult_post_routes(tmp_path: Path) -> None:
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


def _write_entity_index(project_root: Path) -> None:
    _write_json(
        _entity_artifact_root(project_root) / "entities.json",
        {
            "items": [
                {
                    "entity_id": "ENT_STOCK_600519.SH",
                    "display_name": "Kweichow Moutai",
                    "entity_type": "stock",
                    "aliases": ["600519.SH", "Moutai"],
                    "profile": {
                        "canonical_entity": {
                            "canonical_entity_id": "ENT_STOCK_600519.SH",
                            "entity_type": "stock",
                            "display_name": "Kweichow Moutai",
                            "market": "CN-A",
                            "anchor_code": "600519.SH",
                            "status": "active",
                        },
                        "aliases": [
                            {"alias_text": "600519.SH", "alias_type": "ticker"}
                        ],
                        "cross_listing_group": None,
                        "cross_listing_entity_ids": [],
                    },
                },
                {
                    "entity_id": "ENT_STOCK_300750.SZ",
                    "display_name": "CATL",
                    "entity_type": "stock",
                    "aliases": ["300750.SZ", "CATL"],
                    "profile": {
                        "canonical_entity": {
                            "canonical_entity_id": "ENT_STOCK_300750.SZ",
                            "entity_type": "stock",
                            "display_name": "CATL",
                            "market": "CN-A",
                            "anchor_code": "300750.SZ",
                            "status": "active",
                        },
                        "aliases": [
                            {"alias_text": "300750.SZ", "alias_type": "ticker"}
                        ],
                        "cross_listing_group": None,
                        "cross_listing_entity_ids": [],
                    },
                },
            ]
        },
    )


def _write_data_artifact(
    project_root: Path,
    *,
    namespace: str,
    name: str,
    columns: list[str],
    items: list[dict[str, object]],
) -> None:
    _write_json(
        _data_artifact_root(project_root) / namespace / f"{name}.json",
        {"columns": columns, "items": items},
    )


def _entity_artifact_root(project_root: Path) -> Path:
    return project_root / "entity-registry" / "artifacts" / "frontend-api"


def _data_artifact_root(project_root: Path) -> Path:
    return project_root / "data-platform" / "artifacts" / "frontend-api" / "data"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
