from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_SURFACE_FILES = (
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "cycle.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "graph.py",
    PROJECT_ROOT / "src" / "frontend_api" / "routes" / "operations.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "data_platform_adapter.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "graph_adapter.py",
    PROJECT_ROOT / "src" / "frontend_api" / "adapters" / "operations_adapter.py",
)
FORBIDDEN_SOURCE_TOKENS = ("stg_tushare_", "doc_api", "tushare_")


def test_business_readonly_surfaces_do_not_depend_on_tushare_source_contracts() -> None:
    violations: list[str] = []
    for path in BUSINESS_SURFACE_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} contains {token}")

    assert violations == []
