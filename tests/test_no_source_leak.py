from __future__ import annotations

from pathlib import Path

from frontend_api.adapters.data_platform_adapter import DataPlatformReadAdapter
from frontend_api.app import create_app
from frontend_api.settings import FrontendApiSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_SURFACE_FILES = (
    PROJECT_ROOT / "src" / "frontend_api" / "public.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "entity_data.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "cycle.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "graph.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "operations.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "data_platform_adapter.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "graph_adapter.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "operations_adapter.py",
)
FORBIDDEN_SOURCE_TOKENS = ("stg_tushare_", "doc_api", "tushare_")
FORBIDDEN_DEFAULT_ROUTE_TOKENS = (
    "/api/project-ult/data/raw/{source}",
    "/api/project-ult/debug/data/raw/{source}",
)


def test_business_readonly_surfaces_do_not_depend_on_tushare_source_contracts() -> None:
    violations: list[str] = []
    for path in BUSINESS_SURFACE_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} contains {token}")

    assert violations == []


def test_default_readonly_surface_does_not_mount_raw_debug_routes(tmp_path: Path) -> None:
    app = create_app(FrontendApiSettings(project_root=tmp_path))
    route_paths = {route.path for route in app.routes}

    assert "/api/project-ult/data/raw/{source}" not in route_paths
    assert "/api/project-ult/debug/data/raw/{source}" not in route_paths


def test_public_contract_excludes_raw_debug_routes() -> None:
    public_text = (PROJECT_ROOT / "src" / "frontend_api" / "public.py").read_text(
        encoding="utf-8"
    )

    for token in FORBIDDEN_DEFAULT_ROUTE_TOKENS:
        assert token not in public_text


def test_data_platform_public_api_fallback_is_disabled_by_default(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path)
    adapter = DataPlatformReadAdapter(project_root=tmp_path)

    assert settings.allow_data_platform_public_api_fallback is False
    assert adapter.allow_public_api_fallback is False
    assert adapter._load_public_callable("data_platform.cycle", "list_cycles") == (
        None,
        "data-platform public API fallback disabled",
    )
