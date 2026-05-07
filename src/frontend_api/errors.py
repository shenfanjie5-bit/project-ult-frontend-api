"""Error envelope helpers for the frontend API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


_LOGGER = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ProjectUltApiError(Exception):
    """Raised when a route cannot satisfy the stable API contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _redact_internal_paths(
    details: Mapping[str, Any],
    project_root: Path | None,
) -> dict[str, Any]:
    """Strip absolute filesystem prefixes from path-like values so error
    envelopes don't leak server-side directory layout to clients (audit L7).

    Behavior:
    - Absolute filesystem paths (start with ``/``) become relative to
      ``project_root`` when possible, else are reduced to the basename.
    - Module:function references like ``data_platform.cycle:list_cycles``
      pass through unchanged (no leading ``/``, contains ``:``).
    - Other values pass through unchanged.

    The full absolute path is logged at WARNING for server-side
    debugging — only the client-facing copy is redacted.
    """

    redacted: dict[str, Any] = {}
    leaked_paths: dict[str, str] = {}

    for key, value in details.items():
        if not isinstance(value, str) or not value.startswith("/"):
            redacted[key] = value
            continue

        absolute = Path(value)
        replacement: str | None = None
        if project_root is not None:
            try:
                replacement = str(absolute.relative_to(project_root))
            except ValueError:
                replacement = None
        if replacement is None:
            replacement = absolute.name  # outside project_root — basename only

        redacted[key] = replacement
        leaked_paths[key] = value

    if leaked_paths:
        _LOGGER.warning(
            "frontend-api error details: redacted absolute filesystem paths "
            "from client envelope (server-side originals: %s)",
            leaked_paths,
        )

    return redacted


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectUltApiError)
    async def _handle_project_ult_error(
        request: Request,
        exc: ProjectUltApiError,
    ) -> JSONResponse:
        settings = getattr(request.app.state, "settings", None)
        project_root = getattr(settings, "project_root", None)
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=_redact_internal_paths(exc.details, project_root),
                request_id=_request_id(request),
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(mode="json"),
        )


def _request_id(request: Request) -> str:
    header_value = request.headers.get("x-request-id")
    if header_value:
        return header_value

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"req_{timestamp}"
