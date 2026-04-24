from __future__ import annotations

import os
from pathlib import Path

from frontend_api import public

PROJECT_ROOT = Path(
    os.getenv("PROJECT_ULT_TEST_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).resolve()


def test_public_health_probe_reports_readable_artifacts(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROJECT_ULT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("PROJECT_ULT_PROFILE", "lite-local")

    result = public.health_probe.check(timeout_sec=1.0)

    assert result["module_id"] == "frontend-api"
    assert result["status"] == "healthy"
    assert result["details"]["module_count"] >= 14


def test_public_smoke_hook_checks_api1_readonly_contract(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROJECT_ULT_ROOT", str(PROJECT_ROOT))

    result = public.smoke_hook.run(profile_id="lite-local")

    assert result["module_id"] == "frontend-api"
    assert result["passed"] is True
    assert result["failure_reason"] is None


def test_public_version_declaration_matches_registry_target() -> None:
    result = public.version_declaration.declare()

    assert result == {
        "module_id": "frontend-api",
        "module_version": "0.1.0",
        "contract_version": "v0.1.3",
        "compatible_contract_range": ">=0.1.0,<0.2.0",
    }
