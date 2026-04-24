from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from frontend_api.app import create_app
from frontend_api.settings import FrontendApiSettings


PROJECT_ROOT = Path(
    os.getenv("PROJECT_ULT_TEST_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).resolve()


def _client() -> TestClient:
    app = create_app(
        FrontendApiSettings(
            project_root=PROJECT_ROOT,
            profile="lite-local",
            mode="lite-local",
        )
    )
    return TestClient(app)


def test_system_routes_return_real_assembly_artifacts() -> None:
    client = _client()

    health = client.get("/api/project-ult/health")
    modules = client.get("/api/project-ult/modules")
    profiles = client.get("/api/project-ult/profiles")
    compat = client.get("/api/project-ult/compat")

    assert health.status_code == 200
    assert modules.status_code == 200
    assert profiles.status_code == 200
    assert compat.status_code == 200
    assert health.json()["status"] == "healthy"
    assert modules.json()["total"] >= 12
    assert profiles.json()["active_profile"] == "lite-local"
    assert compat.json()["statuses"]["verified"] >= 1


def test_api1_does_not_register_command_routes() -> None:
    client = _client()
    route_methods = {
        (route.path, method)
        for route in client.app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/project-ult/compat/run", "POST") not in route_methods
    assert ("/api/project-ult/smoke/{module_id}", "POST") not in route_methods
    assert all(
        method != "POST" or not path.startswith("/api/project-ult")
        for path, method in route_methods
    )


def test_vite_cors_preflight_is_allowed() -> None:
    client = _client()

    response = client.options(
        "/api/project-ult/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "GET" in response.headers["access-control-allow-methods"]


def test_artifact_schema_errors_use_error_envelope(tmp_path: Path) -> None:
    assembly_root = tmp_path / "assembly"
    assembly_root.mkdir()
    (assembly_root / "profiles").mkdir()
    (assembly_root / "compatibility-matrix.yaml").write_text("[]\n", encoding="utf-8")
    (assembly_root / "module-registry.yaml").write_text(
        "- module_id: broken\n",
        encoding="utf-8",
    )
    app = create_app(
        FrontendApiSettings(
            project_root=tmp_path,
            profile="lite-local",
            mode="lite-local",
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/project-ult/modules",
        headers={"x-request-id": "req_test_schema"},
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "PROJECT_ULT_MODULE_REGISTRY_SCHEMA_INVALID"
    assert payload["error"]["request_id"] == "req_test_schema"
    assert payload["error"]["details"]["index"] == 0
    assert payload["error"]["details"]["path"].endswith("module-registry.yaml")
