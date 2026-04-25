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


def test_operations_routes_read_api4a_artifacts(tmp_path: Path) -> None:
    _write_api4a_artifacts(tmp_path)
    client = _client(tmp_path)

    providers = client.get("/api/project-ult/reasoner/providers")
    results = client.get(
        "/api/project-ult/reasoner/results?limit=1&cycle_id=CYCLE_20260424"
    )
    audit = client.get("/api/project-ult/audit/CYCLE_20260424")
    replay = client.get("/api/project-ult/replay/CYCLE_20260424")
    backtests = client.get("/api/project-ult/backtests?limit=1")
    backtest = client.get("/api/project-ult/backtests/BT_API4A_001")
    runs = client.get("/api/project-ult/orchestrator/runs?limit=1&status=success")
    run = client.get("/api/project-ult/orchestrator/runs/RUN_API4A_001")

    assert providers.status_code == 200
    providers_payload = providers.json()
    assert providers_payload["source_status"] == "available"
    assert providers_payload["total"] == 2
    assert providers_payload["items"][0]["provider_id"] == (
        "reasoner_primary_structured"
    )

    assert results.status_code == 200
    results_payload = results.json()
    assert results_payload["source_status"] == "available"
    assert results_payload["total"] == 2
    assert results_payload["next_cursor"] == "1"
    assert results_payload["items"][0]["cycle_id"] == "CYCLE_20260424"

    assert audit.status_code == 200
    audit_payload = audit.json()
    assert audit_payload["source_status"] == "available"
    assert audit_payload["payload"]["cycle_id"] == "CYCLE_20260424"
    assert audit_payload["metadata"]["contract"] == "api-4a-readonly"

    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload["source_status"] == "available"
    assert replay_payload["payload"]["replay_mode"] == "read_history"
    assert replay_payload["metadata"]["contract"] == "api-4a-readonly"

    assert backtests.status_code == 200
    backtests_payload = backtests.json()
    assert backtests_payload["source_status"] == "available"
    assert backtests_payload["total"] == 2
    assert backtests_payload["next_cursor"] == "1"
    assert backtests_payload["items"][0]["backtest_id"] == "BT_API4A_001"

    assert backtest.status_code == 200
    backtest_payload = backtest.json()
    assert backtest_payload["source_status"] == "available"
    assert backtest_payload["payload"]["metric_summary"]["ic_mean"] == 0.04
    assert backtest_payload["metadata"]["contract"] == "api-4a-readonly"

    assert runs.status_code == 200
    runs_payload = runs.json()
    assert runs_payload["source_status"] == "available"
    assert runs_payload["total"] == 1
    assert runs_payload["items"][0]["run_id"] == "RUN_API4A_001"

    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["source_status"] == "available"
    assert run_payload["payload"]["run_id"] == "RUN_API4A_001"
    assert run_payload["metadata"]["contract"] == "api-4a-readonly"


def test_project_artifacts_return_api4a_success_state() -> None:
    client = _client(PROJECT_ROOT)

    providers = client.get("/api/project-ult/reasoner/providers")
    results = client.get("/api/project-ult/reasoner/results?limit=1")
    audit = client.get("/api/project-ult/audit/CYCLE_20260424")
    replay = client.get("/api/project-ult/replay/CYCLE_20260424")
    backtests = client.get("/api/project-ult/backtests?limit=1")
    backtest = client.get("/api/project-ult/backtests/BT_API4A_001")
    runs = client.get("/api/project-ult/orchestrator/runs?limit=1")
    run = client.get("/api/project-ult/orchestrator/runs/RUN_API4A_001")

    assert providers.status_code == 200
    assert providers.json()["source_status"] == "available"
    assert providers.json()["items"][0]["provider_id"] == "reasoner_primary_structured"
    assert results.status_code == 200
    assert results.json()["source_status"] == "available"
    assert results.json()["items"][0]["result_id"] == (
        "reasoner_result_cycle_20260424_001"
    )
    assert audit.status_code == 200
    assert audit.json()["payload"]["gate_status"] == "passed"
    assert replay.status_code == 200
    assert replay.json()["payload"]["snapshot_id"] == "api4a_replay_cycle_20260424"
    assert backtests.status_code == 200
    assert backtests.json()["items"][0]["backtest_id"] == "BT_API4A_001"
    assert backtest.status_code == 200
    assert backtest.json()["payload"]["backtest_id"] == "BT_API4A_001"
    assert runs.status_code == 200
    assert runs.json()["items"][0]["run_id"] == "RUN_API4A_001"
    assert run.status_code == 200
    assert run.json()["payload"]["run_id"] == "RUN_API4A_001"


def test_operations_list_routes_return_unavailable_without_sources(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    responses = [
        client.get("/api/project-ult/reasoner/providers"),
        client.get("/api/project-ult/reasoner/results"),
        client.get("/api/project-ult/backtests"),
        client.get("/api/project-ult/orchestrator/runs"),
    ]

    for response in responses:
        assert response.status_code == 200
        payload = response.json()
        assert payload["source_status"] == "unavailable"
        assert payload["items"] == []
        assert payload["total"] == 0
        assert payload["next_cursor"] is None


def test_operations_detail_routes_return_source_unavailable_without_sources(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    responses = {
        "PROJECT_ULT_AUDIT_SOURCE_UNAVAILABLE": client.get(
            "/api/project-ult/audit/CYCLE_20260424",
            headers={"x-request-id": "req_audit_source"},
        ),
        "PROJECT_ULT_REPLAY_SOURCE_UNAVAILABLE": client.get(
            "/api/project-ult/replay/CYCLE_20260424",
            headers={"x-request-id": "req_replay_source"},
        ),
        "PROJECT_ULT_BACKTEST_SOURCE_UNAVAILABLE": client.get(
            "/api/project-ult/backtests/BT_API4A_001",
            headers={"x-request-id": "req_backtest_source"},
        ),
        "PROJECT_ULT_ORCHESTRATOR_SOURCE_UNAVAILABLE": client.get(
            "/api/project-ult/orchestrator/runs/RUN_API4A_001",
            headers={"x-request-id": "req_orchestrator_source"},
        ),
    }

    for code, response in responses.items():
        assert response.status_code == 503
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"].startswith("req_")


def test_operations_detail_not_found_is_distinct_from_source_unavailable(
    tmp_path: Path,
) -> None:
    _audit_root(tmp_path).joinpath("audit").mkdir(parents=True)
    _audit_root(tmp_path).joinpath("replay").mkdir(parents=True)
    _audit_root(tmp_path).joinpath("backtests").mkdir(parents=True)
    _orchestrator_root(tmp_path).joinpath("runs").mkdir(parents=True)
    client = _client(tmp_path)

    responses = {
        "PROJECT_ULT_AUDIT_NOT_FOUND": client.get(
            "/api/project-ult/audit/CYCLE_UNKNOWN"
        ),
        "PROJECT_ULT_REPLAY_NOT_FOUND": client.get(
            "/api/project-ult/replay/CYCLE_UNKNOWN"
        ),
        "PROJECT_ULT_BACKTEST_NOT_FOUND": client.get(
            "/api/project-ult/backtests/BT_UNKNOWN"
        ),
        "PROJECT_ULT_ORCHESTRATOR_RUN_NOT_FOUND": client.get(
            "/api/project-ult/orchestrator/runs/RUN_UNKNOWN"
        ),
    }

    for code, response in responses.items():
        assert response.status_code == 404
        assert response.json()["error"]["code"] == code


def test_operations_schema_drift_uses_error_envelope(tmp_path: Path) -> None:
    _write_json(_reasoner_root(tmp_path) / "providers.json", {"items": "bad"})
    _write_json(
        _audit_root(tmp_path) / "audit" / "CYCLE_20260424.json",
        {"cycle_id": "CYCLE_20260424", "metadata": "bad"},
    )
    client = _client(tmp_path)

    providers = client.get(
        "/api/project-ult/reasoner/providers",
        headers={"x-request-id": "req_bad_providers"},
    )
    audit = client.get(
        "/api/project-ult/audit/CYCLE_20260424",
        headers={"x-request-id": "req_bad_audit"},
    )

    assert providers.status_code == 500
    assert providers.json()["error"]["code"] == (
        "PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID"
    )
    assert providers.json()["error"]["request_id"] == "req_bad_providers"
    assert audit.status_code == 500
    assert audit.json()["error"]["code"] == (
        "PROJECT_ULT_AUDIT_ARTIFACT_SCHEMA_INVALID"
    )
    assert audit.json()["error"]["request_id"] == "req_bad_audit"


def test_operations_invalid_json_uses_error_envelope(tmp_path: Path) -> None:
    path = _orchestrator_root(tmp_path) / "runs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    client = _client(tmp_path)

    response = client.get(
        "/api/project-ult/orchestrator/runs",
        headers={"x-request-id": "req_bad_runs_json"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == (
        "PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID"
    )
    assert response.json()["error"]["request_id"] == "req_bad_runs_json"


def test_operations_openapi_contract_exposes_api4a_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)

    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]

    assert paths.keys() >= {
        "/api/project-ult/reasoner/providers",
        "/api/project-ult/reasoner/results",
        "/api/project-ult/audit/{cycle_id}",
        "/api/project-ult/replay/{cycle_id}",
        "/api/project-ult/backtests",
        "/api/project-ult/backtests/{backtest_id}",
        "/api/project-ult/orchestrator/runs",
        "/api/project-ult/orchestrator/runs/{run_id}",
    }
    assert _query_schema(paths, "/api/project-ult/reasoner/results", "limit")[
        "maximum"
    ] == 500
    assert _query_schema(paths, "/api/project-ult/backtests", "limit")[
        "maximum"
    ] == 500
    assert _query_schema(paths, "/api/project-ult/orchestrator/runs", "limit")[
        "maximum"
    ] == 500
    assert _query_schema(paths, "/api/project-ult/reasoner/results", "cursor")[
        "anyOf"
    ][1] == {"type": "null"}
    assert _query_schema(paths, "/api/project-ult/orchestrator/runs", "status")[
        "anyOf"
    ][1] == {"type": "null"}


def test_operations_limit_bounds_use_fastapi_validation(tmp_path: Path) -> None:
    client = _client(tmp_path)

    responses = [
        client.get("/api/project-ult/reasoner/results?limit=501"),
        client.get("/api/project-ult/backtests?limit=501"),
        client.get("/api/project-ult/orchestrator/runs?limit=501"),
    ]

    for response in responses:
        assert response.status_code == 422


def test_operations_routes_reject_invalid_query(tmp_path: Path) -> None:
    client = _client(tmp_path)

    cursor_response = client.get(
        "/api/project-ult/reasoner/results?cursor=not-an-offset"
    )
    cycle_response = client.get("/api/project-ult/audit/../secret")
    encoded_cycle_response = client.get("/api/project-ult/audit/bad%20cycle")
    backtest_response = client.get("/api/project-ult/backtests/bad%20backtest")
    run_response = client.get("/api/project-ult/orchestrator/runs/bad%20run")
    status_response = client.get(
        "/api/project-ult/orchestrator/runs?status=../secret"
    )

    assert cursor_response.status_code == 400
    assert cursor_response.json()["error"]["code"] == "PROJECT_ULT_CURSOR_INVALID"
    assert cycle_response.status_code == 404
    assert encoded_cycle_response.status_code == 400
    assert encoded_cycle_response.json()["error"]["code"] == (
        "PROJECT_ULT_IDENTIFIER_INVALID"
    )
    assert backtest_response.status_code == 400
    assert backtest_response.json()["error"]["code"] == (
        "PROJECT_ULT_IDENTIFIER_INVALID"
    )
    assert run_response.status_code == 400
    assert run_response.json()["error"]["code"] == "PROJECT_ULT_IDENTIFIER_INVALID"
    assert status_response.status_code == 400
    assert status_response.json()["error"]["code"] == "PROJECT_ULT_STATUS_INVALID"


def test_operations_all_list_schema_drift_uses_error_envelope(
    tmp_path: Path,
) -> None:
    cases = [
        (
            _reasoner_root(tmp_path) / "providers.json",
            "/api/project-ult/reasoner/providers",
            "PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _reasoner_root(tmp_path) / "results.json",
            "/api/project-ult/reasoner/results",
            "PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "backtests.json",
            "/api/project-ult/backtests",
            "PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _orchestrator_root(tmp_path) / "runs.json",
            "/api/project-ult/orchestrator/runs",
            "PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
        ),
    ]
    for path, route, code in cases:
        _write_json(path, {"items": "bad"})
        client = _client(tmp_path)
        response = client.get(route, headers={"x-request-id": f"req_{code}"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"] == f"req_{code}"
        path.unlink()


def test_operations_all_list_invalid_json_uses_error_envelope(
    tmp_path: Path,
) -> None:
    cases = [
        (
            _reasoner_root(tmp_path) / "providers.json",
            "/api/project-ult/reasoner/providers",
            "PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _reasoner_root(tmp_path) / "results.json",
            "/api/project-ult/reasoner/results",
            "PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "backtests.json",
            "/api/project-ult/backtests",
            "PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _orchestrator_root(tmp_path) / "runs.json",
            "/api/project-ult/orchestrator/runs",
            "PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
        ),
    ]
    for path, route, code in cases:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        client = _client(tmp_path)
        response = client.get(route, headers={"x-request-id": f"req_{code}"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"] == f"req_{code}"
        path.unlink()


def test_operations_all_detail_schema_drift_uses_error_envelope(
    tmp_path: Path,
) -> None:
    cases = [
        (
            _audit_root(tmp_path) / "audit" / "CYCLE_20260424.json",
            "/api/project-ult/audit/CYCLE_20260424",
            "PROJECT_ULT_AUDIT_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "replay" / "CYCLE_20260424.json",
            "/api/project-ult/replay/CYCLE_20260424",
            "PROJECT_ULT_REPLAY_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "backtests" / "BT_API4A_001.json",
            "/api/project-ult/backtests/BT_API4A_001",
            "PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _orchestrator_root(tmp_path) / "runs" / "RUN_API4A_001.json",
            "/api/project-ult/orchestrator/runs/RUN_API4A_001",
            "PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
        ),
    ]
    for path, route, code in cases:
        _write_json(path, {"metadata": "bad"})
        client = _client(tmp_path)
        response = client.get(route, headers={"x-request-id": f"req_{code}"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"] == f"req_{code}"
        path.unlink()


def test_operations_all_detail_invalid_json_uses_error_envelope(
    tmp_path: Path,
) -> None:
    cases = [
        (
            _audit_root(tmp_path) / "audit" / "CYCLE_20260424.json",
            "/api/project-ult/audit/CYCLE_20260424",
            "PROJECT_ULT_AUDIT_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "replay" / "CYCLE_20260424.json",
            "/api/project-ult/replay/CYCLE_20260424",
            "PROJECT_ULT_REPLAY_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _audit_root(tmp_path) / "backtests" / "BT_API4A_001.json",
            "/api/project-ult/backtests/BT_API4A_001",
            "PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
        ),
        (
            _orchestrator_root(tmp_path) / "runs" / "RUN_API4A_001.json",
            "/api/project-ult/orchestrator/runs/RUN_API4A_001",
            "PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
        ),
    ]
    for path, route, code in cases:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        client = _client(tmp_path)
        response = client.get(route, headers={"x-request-id": f"req_{code}"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"] == f"req_{code}"
        path.unlink()


def test_operations_missing_metadata_defaults_to_empty_object(tmp_path: Path) -> None:
    _write_json(
        _reasoner_root(tmp_path) / "results.json",
        {"items": [{"result_id": "result_without_index_metadata"}]},
    )
    _write_json(
        _audit_root(tmp_path) / "audit" / "CYCLE_20260424.json",
        {"cycle_id": "CYCLE_20260424", "audit_records": []},
    )
    client = _client(tmp_path)

    results = client.get("/api/project-ult/reasoner/results")
    audit = client.get("/api/project-ult/audit/CYCLE_20260424")

    assert results.status_code == 200
    assert results.json()["source_status"] == "available"
    assert audit.status_code == 200
    assert audit.json()["metadata"] == {}


def test_api4a_does_not_register_project_ult_post_routes(tmp_path: Path) -> None:
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


def _write_api4a_artifacts(project_root: Path) -> None:
    _write_json(
        _reasoner_root(project_root) / "providers.json",
        {
            "items": [
                {
                    "provider_id": "reasoner_primary_structured",
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "status": "available",
                    "capabilities": ["structured_generation"],
                },
                {
                    "provider_id": "reasoner_standby_structured",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4.5",
                    "status": "standby",
                    "capabilities": ["structured_generation"],
                },
            ],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _reasoner_root(project_root) / "results.json",
        {
            "items": [
                {
                    "result_id": "reasoner_result_cycle_20260424_001",
                    "cycle_id": "CYCLE_20260424",
                    "status": "success",
                    "payload": {"answer": "first"},
                },
                {
                    "result_id": "reasoner_result_cycle_20260424_002",
                    "cycle_id": "CYCLE_20260424",
                    "status": "success",
                    "payload": {"answer": "second"},
                },
            ],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _audit_root(project_root) / "audit" / "CYCLE_20260424.json",
        {
            "cycle_id": "CYCLE_20260424",
            "gate_status": "passed",
            "audit_records": [{"record_id": "AUDIT_API4A_001"}],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _audit_root(project_root) / "replay" / "CYCLE_20260424.json",
        {
            "cycle_id": "CYCLE_20260424",
            "replay_mode": "read_history",
            "objects": [{"object_type": "world_state_snapshot"}],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _audit_root(project_root) / "backtests.json",
        {
            "items": [
                {
                    "backtest_id": "BT_API4A_001",
                    "cycle_id": "CYCLE_20260424",
                    "status": "completed",
                    "metric_summary": {"ic_mean": 0.04},
                },
                {
                    "backtest_id": "BT_API4A_002",
                    "cycle_id": "CYCLE_20260424",
                    "status": "completed",
                    "metric_summary": {"ic_mean": 0.03},
                },
            ],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _audit_root(project_root) / "backtests" / "BT_API4A_001.json",
        {
            "backtest_id": "BT_API4A_001",
            "cycle_id": "CYCLE_20260424",
            "metric_summary": {"ic_mean": 0.04},
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _orchestrator_root(project_root) / "runs.json",
        {
            "items": [
                {
                    "run_id": "RUN_API4A_001",
                    "cycle_id": "CYCLE_20260424",
                    "status": "success",
                    "phases": [{"phase": "formal_snapshot_read"}],
                },
                {
                    "run_id": "RUN_API4A_002",
                    "cycle_id": "CYCLE_20260424",
                    "status": "running",
                    "phases": [{"phase": "reasoner_read"}],
                },
            ],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )
    _write_json(
        _orchestrator_root(project_root) / "runs" / "RUN_API4A_001.json",
        {
            "run_id": "RUN_API4A_001",
            "cycle_id": "CYCLE_20260424",
            "status": "success",
            "steps": [{"step_id": "formal_snapshot_read"}],
            "metadata": {"contract": "api-4a-readonly"},
        },
    )


def _reasoner_root(project_root: Path) -> Path:
    return project_root / "reasoner-runtime" / "artifacts" / "frontend-api"


def _audit_root(project_root: Path) -> Path:
    return project_root / "audit-eval" / "artifacts" / "frontend-api"


def _orchestrator_root(project_root: Path) -> Path:
    return project_root / "orchestrator" / "artifacts" / "frontend-api"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _query_schema(
    openapi_paths: dict[str, object],
    path: str,
    name: str,
) -> dict[str, object]:
    parameters = openapi_paths[path]["get"]["parameters"]  # type: ignore[index]
    for parameter in parameters:
        if parameter["name"] == name:
            return parameter["schema"]
    raise AssertionError(f"missing query parameter {name} on {path}")
