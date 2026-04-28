"""Runtime settings for the frontend API."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


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
        )


def _parse_bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
