from __future__ import annotations

import os
from pathlib import Path

from frontend_api.adapters.assembly_adapter import AssemblyAdapter


PROJECT_ROOT = Path(
    os.getenv("PROJECT_ULT_TEST_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).resolve()


def test_modules_are_loaded_from_assembly_registry_artifact() -> None:
    adapter = AssemblyAdapter(
        project_root=PROJECT_ROOT,
        active_profile="lite-local",
        mode="lite-local",
    )

    response = adapter.list_modules()

    module_ids = {item.module_id for item in response.items}
    assert response.total == len(response.items)
    assert "assembly" in module_ids
    assert "frontend-api" not in module_ids
    assert response.statuses["verified"] >= 1


def test_profiles_include_default_compatibility_evidence() -> None:
    adapter = AssemblyAdapter(
        project_root=PROJECT_ROOT,
        active_profile="lite-local",
        mode="lite-local",
    )

    response = adapter.list_profiles()

    lite_local = next(
        item for item in response.items if item.profile_id == "lite-local"
    )
    assert lite_local.compatibility.status == "verified"
    assert lite_local.compatibility.verified_at == "2026-04-24T05:24:14Z"


def test_health_reports_active_profile_artifact_status() -> None:
    adapter = AssemblyAdapter(
        project_root=PROJECT_ROOT,
        active_profile="lite-local",
        mode="lite-local",
    )

    response = adapter.health()

    assert response.status == "healthy"
    assert response.modules.total >= 1
    assert response.profiles.details["active_profile_found"] is True
    assert response.compatibility.details["active_verified_rows"] >= 1
