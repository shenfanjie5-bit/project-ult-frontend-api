from __future__ import annotations

import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_IMPORTS = {
    "assembly",
    "audit_eval",
    "contracts",
    "data_platform",
    "entity_registry",
    "feature_store",
    "graph_engine",
    "main_core",
    "orchestrator",
    "reasoner_runtime",
    "stream_layer",
    "subsystem_announcement",
    "subsystem_news",
    "subsystem_sdk",
}


def test_frontend_api_does_not_import_sibling_modules_or_assembly_impl() -> None:
    offenders: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported = _imported_module(node)
            if imported is None:
                continue
            root_name = imported.split(".", 1)[0]
            if root_name in FORBIDDEN_IMPORTS:
                offenders.append(f"{path}: {imported}")

    assert offenders == []


def _imported_module(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name
    if isinstance(node, ast.ImportFrom) and node.module:
        return node.module
    return None
