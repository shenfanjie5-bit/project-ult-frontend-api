"""Error envelope helpers for the frontend API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectUltApiError)
    async def _handle_project_ult_error(
        request: Request,
        exc: ProjectUltApiError,
    ) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
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
