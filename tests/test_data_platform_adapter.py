from __future__ import annotations

import json
from pathlib import Path

import pytest

from frontend_api.adapters.data_platform_adapter import DataPlatformReadAdapter
from frontend_api.errors import ProjectUltApiError


def test_list_cycles_reads_artifact_index(tmp_path: Path) -> None:
    _write_json(
        _artifact_root(tmp_path) / "cycles.json",
        {
            "items": [
                {
                    "cycle_id": "CYCLE_20260424",
                    "status": "published",
                    "cycle_date": "2026-04-24",
                    "manifest": {
                        "manifest_ref": "manifest/CYCLE_20260424",
                        "formal_table_snapshots": {
                            "formal.world_state_snapshot": {"snapshot_id": 123}
                        },
                    },
                }
            ]
        },
    )

    response = DataPlatformReadAdapter(project_root=tmp_path).list_cycles()

    assert response.source_status == "available"
    assert response.total == 1
    assert response.items[0].cycle_id == "CYCLE_20260424"
    assert response.items[0].manifest is not None
    assert response.items[0].manifest.manifest_ref == "manifest/CYCLE_20260424"


def test_get_cycle_reads_detail_artifact(tmp_path: Path) -> None:
    _write_json(
        _artifact_root(tmp_path) / "cycles" / "CYCLE_20260424.json",
        {
            "cycle_id": "CYCLE_20260424",
            "status": "phase3",
            "candidate_count": 7,
        },
    )

    cycle = DataPlatformReadAdapter(project_root=tmp_path).get_cycle("CYCLE_20260424")

    assert cycle.status == "phase3"
    assert cycle.candidate_count == 7


def test_formal_latest_reads_artifact(tmp_path: Path) -> None:
    _write_json(
        _artifact_root(tmp_path)
        / "formal"
        / "world_state_snapshot"
        / "latest.json",
        {
            "object_type": "world_state_snapshot",
            "cycle_id": "CYCLE_20260424",
            "snapshot_id": 123,
            "payload": {"entities": [{"entity_id": "ENT_STOCK_000001.SZ"}]},
        },
    )

    response = DataPlatformReadAdapter(project_root=tmp_path).get_formal_object(
        "world_state_snapshot"
    )

    assert response.source_status == "available"
    assert response.cycle_id == "CYCLE_20260424"
    assert response.payload["entities"][0]["entity_id"] == "ENT_STOCK_000001.SZ"


def test_latest_manifest_reads_artifact(tmp_path: Path) -> None:
    _write_json(
        _artifact_root(tmp_path) / "manifests" / "latest.json",
        {
            "published_cycle_id": "CYCLE_20260424",
            "published_at": "2026-04-24T06:51:23Z",
            "formal_table_snapshots": {
                "formal.recommendation_snapshot": {"snapshot_id": 456}
            },
        },
    )

    response = DataPlatformReadAdapter(project_root=tmp_path).get_latest_manifest()

    assert response.source_status == "available"
    assert response.cycle_id == "CYCLE_20260424"
    assert response.formal_table_snapshots["formal.recommendation_snapshot"] == {
        "snapshot_id": 456
    }


def test_list_cycles_degrades_to_empty_when_no_public_source(tmp_path: Path) -> None:
    response = DataPlatformReadAdapter(project_root=tmp_path).list_cycles()

    assert response.source_status == "unavailable"
    assert response.total == 0
    assert response.items == []
    assert response.message is not None


def test_missing_formal_source_raises_project_ult_error(tmp_path: Path) -> None:
    adapter = DataPlatformReadAdapter(project_root=tmp_path)

    with pytest.raises(ProjectUltApiError) as exc_info:
        adapter.get_formal_object("world_state_snapshot")

    assert exc_info.value.code == "PROJECT_ULT_FORMAL_SOURCE_UNAVAILABLE"
    assert exc_info.value.status_code == 503
    assert "data_platform.serving:get_formal_latest" in (
        exc_info.value.details["public_api"]
    )


def test_cycle_artifact_schema_errors_use_project_ult_error(tmp_path: Path) -> None:
    _write_json(_artifact_root(tmp_path) / "cycles.json", {"items": [{"status": "phase0"}]})

    with pytest.raises(ProjectUltApiError) as exc_info:
        DataPlatformReadAdapter(project_root=tmp_path).list_cycles()

    assert exc_info.value.code == "PROJECT_ULT_CYCLE_ARTIFACT_SCHEMA_INVALID"
    assert exc_info.value.status_code == 500
    assert exc_info.value.details["index"] == 0


def test_public_cycle_schema_errors_are_not_downgraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = DataPlatformReadAdapter(project_root=tmp_path)

    def fake_load_public_callable(module_name: str, attr_name: str):
        assert (module_name, attr_name) == ("data_platform.cycle", "list_cycles")
        return lambda: [{"status": "phase0"}], None

    monkeypatch.setattr(adapter, "_load_public_callable", fake_load_public_callable)

    with pytest.raises(ProjectUltApiError) as exc_info:
        adapter.list_cycles()

    assert exc_info.value.code == "PROJECT_ULT_CYCLE_SOURCE_SCHEMA_INVALID"
    assert exc_info.value.status_code == 500
    assert exc_info.value.details["index"] == 0
    assert exc_info.value.details["path"] == "data_platform.cycle:list_cycles"


def test_public_formal_schema_errors_are_not_downgraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = DataPlatformReadAdapter(project_root=tmp_path)

    def fake_load_public_callable(module_name: str, attr_name: str):
        assert (module_name, attr_name) == (
            "data_platform.serving",
            "get_formal_latest",
        )
        return (
            lambda object_type: {
                "object_type": object_type,
                "cycle_id": [],
                "payload": {},
            },
            None,
        )

    monkeypatch.setattr(adapter, "_load_public_callable", fake_load_public_callable)

    with pytest.raises(ProjectUltApiError) as exc_info:
        adapter.get_formal_object("world_state_snapshot")

    assert exc_info.value.code == "PROJECT_ULT_FORMAL_SOURCE_SCHEMA_INVALID"
    assert exc_info.value.status_code == 500


def test_public_manifest_schema_errors_are_not_downgraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = DataPlatformReadAdapter(project_root=tmp_path)

    def fake_load_public_callable(module_name: str, attr_name: str):
        assert (module_name, attr_name) == (
            "data_platform.cycle",
            "get_latest_publish_manifest",
        )
        return lambda: [], None

    monkeypatch.setattr(adapter, "_load_public_callable", fake_load_public_callable)

    with pytest.raises(ProjectUltApiError) as exc_info:
        adapter.get_latest_manifest()

    assert exc_info.value.code == "PROJECT_ULT_MANIFEST_SOURCE_SCHEMA_INVALID"
    assert exc_info.value.status_code == 500


def _artifact_root(project_root: Path) -> Path:
    return project_root / "data-platform" / "artifacts" / "frontend-api"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
