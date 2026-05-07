"""Stage 3 security-boundary tests: H3 deployment guard + L7 path redaction."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pytest

from frontend_api.app import create_app
from frontend_api.errors import _redact_internal_paths
from frontend_api.settings import (
    FrontendApiSecurityError,
    FrontendApiSettings,
)


# ---------------------------------------------------------------------------
# H3: frontend-api refuses to bind on non-loopback host without opt-out
# ---------------------------------------------------------------------------


def test_loopback_host_passes_safe_to_serve(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="127.0.0.1")
    settings.assert_safe_to_serve()  # must not raise


def test_localhost_alias_passes_safe_to_serve(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="localhost")
    settings.assert_safe_to_serve()  # must not raise


def test_ipv6_loopback_passes_safe_to_serve(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="::1")
    settings.assert_safe_to_serve()  # must not raise


def test_non_loopback_host_refuses_without_opt_out(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="0.0.0.0")
    with pytest.raises(FrontendApiSecurityError, match="non-loopback"):
        settings.assert_safe_to_serve()


def test_public_ip_host_refuses_without_opt_out(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="10.0.1.5")
    with pytest.raises(FrontendApiSecurityError, match="non-loopback"):
        settings.assert_safe_to_serve()


def test_explicit_opt_out_allows_non_loopback_host(tmp_path: Path) -> None:
    settings = FrontendApiSettings(
        project_root=tmp_path,
        host="0.0.0.0",
        require_loopback_or_auth_proxy=False,
    )
    settings.assert_safe_to_serve()  # must not raise


def test_create_app_invokes_safe_to_serve_guard(tmp_path: Path) -> None:
    settings = FrontendApiSettings(project_root=tmp_path, host="0.0.0.0")
    with pytest.raises(FrontendApiSecurityError):
        create_app(settings)


def test_create_app_passes_when_opted_out(tmp_path: Path) -> None:
    settings = FrontendApiSettings(
        project_root=tmp_path,
        host="0.0.0.0",
        require_loopback_or_auth_proxy=False,
    )
    app = create_app(settings)
    assert app.title == "Project ULT Frontend API"


def test_app_module_import_does_not_construct_guarded_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROJECT_ULT_FRONTEND_API_HOST", "0.0.0.0")
    monkeypatch.delenv("PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY", raising=False)

    module = importlib.import_module("frontend_api.app")
    reloaded = importlib.reload(module)

    assert callable(reloaded.create_app)


def test_from_env_defaults_to_require_auth_proxy_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY", raising=False)
    settings = FrontendApiSettings.from_env()
    assert settings.require_loopback_or_auth_proxy is True


def test_from_env_respects_explicit_false_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY", "false")
    settings = FrontendApiSettings.from_env()
    assert settings.require_loopback_or_auth_proxy is False


# ---------------------------------------------------------------------------
# L7: error envelope redacts absolute filesystem paths
# ---------------------------------------------------------------------------


def test_redact_strips_absolute_path_to_relative(tmp_path: Path) -> None:
    project_root = tmp_path
    nested = project_root / "main-core" / "PROJECT_REPORT.md"
    details = {"path": str(nested), "actual_type": "dict"}

    redacted = _redact_internal_paths(details, project_root)

    assert redacted["path"] == "main-core/PROJECT_REPORT.md"
    assert redacted["actual_type"] == "dict"


def test_redact_falls_back_to_basename_when_outside_project_root(
    tmp_path: Path,
) -> None:
    details = {"path": "/etc/passwd"}

    redacted = _redact_internal_paths(details, tmp_path)

    assert redacted["path"] == "passwd"


def test_redact_passes_through_module_function_strings(tmp_path: Path) -> None:
    """Public-API module:function references are intentionally exposed
    (the test_data_platform_adapter contract relies on them).
    """

    details = {
        "public_api": "data_platform.cycle:list_cycles",
        "path": "data_platform.serving:get_formal_latest",
    }

    redacted = _redact_internal_paths(details, tmp_path)

    assert redacted["public_api"] == "data_platform.cycle:list_cycles"
    assert redacted["path"] == "data_platform.serving:get_formal_latest"


def test_redact_logs_originals_at_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    details = {"path": "/var/lib/secret/internal-file.json"}

    with caplog.at_level(logging.WARNING, logger="frontend_api.errors"):
        _redact_internal_paths(details, tmp_path)

    assert any(
        "/var/lib/secret/internal-file.json" in record.getMessage()
        for record in caplog.records
    )


def test_redact_handles_missing_project_root(tmp_path: Path) -> None:
    details = {"path": "/some/absolute/path/file.json"}
    redacted = _redact_internal_paths(details, project_root=None)

    # No project_root → fall back to basename
    assert redacted["path"] == "file.json"


def test_redact_passes_through_non_string_values(tmp_path: Path) -> None:
    details = {"index": 7, "actual_type": "list", "count": 0}
    redacted = _redact_internal_paths(details, tmp_path)

    assert redacted == {"index": 7, "actual_type": "list", "count": 0}
