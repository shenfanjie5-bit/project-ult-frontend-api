"""Public integration entrypoints for Project ULT assembly.

This module exposes the standard Project ULT public surface:

- ``health_probe``
- ``smoke_hook``
- ``init_hook``
- ``version_declaration``
- ``cli``

Boundary rule: this file does not import assembly. It returns plain dicts so
assembly can validate them against its public protocols from the consumer side.
"""

from __future__ import annotations

import time
from typing import Any

from frontend_api import __version__
from frontend_api.adapters.assembly_adapter import AssemblyAdapter
from frontend_api.app import create_app
from frontend_api.cli import main as cli_main
from frontend_api.settings import FrontendApiSettings

_MODULE_ID = "frontend-api"
_CONTRACT_VERSION = "v0.1.3"
_COMPATIBLE_CONTRACT_RANGE = ">=0.1.0,<0.2.0"
_READONLY_GET_ROUTES = {
    "/api/project-ult/health",
    "/api/project-ult/modules",
    "/api/project-ult/profiles",
    "/api/project-ult/compat",
    "/api/project-ult/cycles",
    "/api/project-ult/cycles/{cycle_id}",
    "/api/project-ult/formal/{object_type}",
    "/api/project-ult/formal/{object_type}/{cycle_id}",
    "/api/project-ult/manifests/latest",
    "/api/project-ult/entities/search",
    "/api/project-ult/entities/{entity_id}",
    "/api/project-ult/data/canonical/{table}",
    "/api/project-ult/data/raw/{source}",
    "/api/project-ult/graph/subgraph",
    "/api/project-ult/graph/paths",
    "/api/project-ult/graph/impact",
    "/api/project-ult/reasoner/providers",
    "/api/project-ult/reasoner/results",
    "/api/project-ult/audit/{cycle_id}",
    "/api/project-ult/replay/{cycle_id}",
    "/api/project-ult/backtests",
    "/api/project-ult/backtests/{backtest_id}",
    "/api/project-ult/orchestrator/runs",
    "/api/project-ult/orchestrator/runs/{run_id}",
    "/api/world-state/latest",
    "/api/pool/latest",
    "/api/recommendations/latest",
}
_PROJECT_ULT_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_SMOKE_COMPATIBLE_STATUSES = {"draft", "verified"}


class _HealthProbe:
    _PROBE_NAME = "frontend-api.system-artifacts"

    def check(self, *, timeout_sec: float) -> dict[str, Any]:
        start = time.monotonic()
        details: dict[str, Any] = {"timeout_sec": timeout_sec}
        try:
            settings = FrontendApiSettings.from_env()
            adapter = AssemblyAdapter(
                project_root=settings.project_root,
                active_profile=settings.profile,
                mode=settings.mode,
            )
            health = adapter.health()
            details.update(
                {
                    "project_root": health.project_root,
                    "active_profile": health.service.active_profile,
                    "artifact_count": len(health.artifacts),
                    "module_count": health.modules.total,
                    "profile_count": health.profiles.total,
                    "compatibility_row_count": health.compatibility.total,
                }
            )
            status = "healthy" if health.status == "healthy" else "degraded"
            message = health.message
        except Exception as exc:  # pragma: no cover - defensive boundary path
            status = "degraded"
            message = f"frontend-api health degraded: {exc}"
            details["error_type"] = type(exc).__name__

        return {
            "module_id": _MODULE_ID,
            "probe_name": self._PROBE_NAME,
            "status": status,
            "latency_ms": max((time.monotonic() - start) * 1000.0, 0.0),
            "message": message,
            "details": details,
        }


class _SmokeHook:
    _HOOK_NAME = "frontend-api.api1-readonly-smoke"

    def run(self, *, profile_id: str) -> dict[str, Any]:
        start = time.monotonic()
        try:
            settings = FrontendApiSettings.from_env().model_copy(
                update={"profile": profile_id, "mode": profile_id}
            )
            app = create_app(settings)
            route_methods = {
                (route.path, method)
                for route in app.routes
                for method in getattr(route, "methods", set())
            }
            missing_routes = sorted(
                route
                for route in _READONLY_GET_ROUTES
                if (route, "GET") not in route_methods
            )
            project_ult_write_routes = sorted(
                f"{method} {path}"
                for path, method in route_methods
                if method in _PROJECT_ULT_WRITE_METHODS
                and path.startswith("/api/project-ult")
            )
            if missing_routes or project_ult_write_routes:
                return _smoke_result(
                    start,
                    passed=False,
                    failure_reason=(
                        "read-only route contract failed: "
                        f"missing_get_routes={missing_routes}, "
                        f"project_ult_write_routes={project_ult_write_routes}"
                    ),
                )

            adapter = AssemblyAdapter(
                project_root=settings.project_root,
                active_profile=profile_id,
                mode=settings.mode,
            )
            missing_artifacts = [
                artifact.kind
                for artifact in adapter._artifact_statuses()
                if not artifact.exists
            ]
            if missing_artifacts:
                return _smoke_result(
                    start,
                    passed=False,
                    failure_reason=(
                        "assembly artifacts are not readable: "
                        f"missing_artifacts={missing_artifacts}"
                    ),
                )
            modules = adapter.list_modules()
            profiles = adapter.list_profiles()
            compatibility = adapter.list_compatibility()
            if not modules.items or not profiles.items or not compatibility.items:
                return _smoke_result(
                    start,
                    passed=False,
                    failure_reason="assembly artifact readers returned empty data",
                )
            active_profile_found = any(
                profile.profile_id == profile_id for profile in profiles.items
            )
            if not active_profile_found:
                return _smoke_result(
                    start,
                    passed=False,
                    failure_reason="active profile manifest not found",
                )
            compatible_default_rows = [
                item
                for item in compatibility.items
                if item.profile_id == profile_id
                and not item.extra_bundles
                and item.status in _SMOKE_COMPATIBLE_STATUSES
            ]
            if not compatible_default_rows:
                return _smoke_result(
                    start,
                    passed=False,
                    failure_reason=(
                        "active profile has no draft or verified default compat row"
                    ),
                )

            return _smoke_result(start, passed=True, failure_reason=None)
        except Exception as exc:
            return _smoke_result(
                start,
                passed=False,
                failure_reason=f"frontend-api smoke failed: {exc}",
            )


class _InitHook:
    def initialize(self, *, resolved_env: dict[str, str]) -> None:
        _ = resolved_env
        return None


class _VersionDeclaration:
    def declare(self) -> dict[str, Any]:
        return {
            "module_id": _MODULE_ID,
            "module_version": __version__,
            "contract_version": _CONTRACT_VERSION,
            "compatible_contract_range": _COMPATIBLE_CONTRACT_RANGE,
        }


class _Cli:
    def invoke(self, argv: list[str]) -> int:
        return int(cli_main(argv) or 0)


def _smoke_result(
    started_at: float,
    *,
    passed: bool,
    failure_reason: str | None,
) -> dict[str, Any]:
    return {
        "module_id": _MODULE_ID,
        "hook_name": _SmokeHook._HOOK_NAME,
        "passed": passed,
        "duration_ms": max((time.monotonic() - started_at) * 1000.0, 0.0),
        "failure_reason": failure_reason,
    }


health_probe: _HealthProbe = _HealthProbe()
smoke_hook: _SmokeHook = _SmokeHook()
init_hook: _InitHook = _InitHook()
version_declaration: _VersionDeclaration = _VersionDeclaration()
cli: _Cli = _Cli()


__all__ = [
    "cli",
    "health_probe",
    "init_hook",
    "smoke_hook",
    "version_declaration",
]
