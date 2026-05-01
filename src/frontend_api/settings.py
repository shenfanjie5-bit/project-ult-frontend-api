"""Runtime settings for the frontend API."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


# Hosts considered loopback-only — safe to bind without an upstream auth
# proxy. Anything else triggers the H3 deployment guard at construction
# time. `0.0.0.0` is intentionally NOT here: it binds to every interface
# and is exactly the case the guard is meant to catch.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class FrontendApiSecurityError(RuntimeError):
    """Raised when frontend-api refuses to bind without an auth boundary."""


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_cors_origins() -> list[str]:
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
    ]


def _parse_csv_env(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


class FrontendApiSettings(BaseModel):
    """Configuration needed by the API-1 read-only routes."""

    project_root: Path = Field(default_factory=_default_project_root)
    profile: str = "lite-local"
    mode: str = "lite-local"
    host: str = "127.0.0.1"
    port: int = 8701
    cors_allow_origins: list[str] = Field(default_factory=_default_cors_origins)
    enable_raw_debug_routes: bool = False
    allow_data_platform_public_api_fallback: bool = False
    # Stage-3 deployment guard (audit H3). The frontend API surface returns
    # audit_record (incl. sanitized_input / raw_output), replay_record,
    # recommendations, reasoner results, and entity data — none of which
    # are safe to expose on shared networks without auth. By default we
    # refuse to bind to a non-loopback host so the unauthenticated sidecar
    # design fails fast on misconfiguration. Operators with an upstream
    # auth proxy must opt out explicitly via
    # PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY=false (or by passing
    # require_loopback_or_auth_proxy=False to FrontendApiSettings).
    require_loopback_or_auth_proxy: bool = True

    @classmethod
    def from_env(cls) -> "FrontendApiSettings":
        profile = os.getenv("PROJECT_ULT_PROFILE", "lite-local")
        return cls(
            project_root=Path(
                os.getenv("PROJECT_ULT_ROOT", str(_default_project_root()))
            ),
            profile=profile,
            mode=os.getenv("PROJECT_ULT_FRONTEND_API_MODE", profile),
            host=os.getenv("PROJECT_ULT_FRONTEND_API_HOST", "127.0.0.1"),
            port=int(os.getenv("PROJECT_ULT_FRONTEND_API_PORT", "8701")),
            cors_allow_origins=_parse_csv_env(
                os.getenv("PROJECT_ULT_FRONTEND_API_CORS_ORIGINS"),
                _default_cors_origins(),
            ),
            enable_raw_debug_routes=_parse_bool_env(
                os.getenv("PROJECT_ULT_FRONTEND_API_ENABLE_RAW_DEBUG_ROUTES"),
            ),
            allow_data_platform_public_api_fallback=_parse_bool_env(
                os.getenv("PROJECT_ULT_FRONTEND_API_ALLOW_PUBLIC_API_FALLBACK"),
            ),
            require_loopback_or_auth_proxy=_parse_bool_env_with_default(
                os.getenv("PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY"),
                default=True,
            ),
        )

    def assert_safe_to_serve(self) -> None:
        """Refuse to construct the app on a non-loopback host unless the
        operator explicitly opted out of the auth-proxy requirement.

        Called at the top of `create_app()` so misconfigured deployments
        fail fast at construction instead of silently exposing internal
        data to shared networks.
        """

        if not self.require_loopback_or_auth_proxy:
            return
        if self.host in _LOOPBACK_HOSTS:
            return
        raise FrontendApiSecurityError(
            f"frontend-api refuses to bind to non-loopback host {self.host!r} "
            "without an explicit auth-proxy opt-out. The API exposes audit / "
            "replay / recommendation data; if an upstream auth proxy is in "
            "place, set PROJECT_ULT_FRONTEND_API_REQUIRE_AUTH_PROXY=false "
            "(or pass require_loopback_or_auth_proxy=False to "
            "FrontendApiSettings)."
        )


def _parse_bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool_env_with_default(value: str | None, *, default: bool) -> bool:
    """Parse a boolean env var that has a non-False default.

    Distinct from `_parse_bool_env` because that helper treats every
    "not-truthy" value (including unset) as False. The H3 guard needs
    True-by-default semantics: unset → secure default; explicit "false"
    → opt-out.
    """

    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default
