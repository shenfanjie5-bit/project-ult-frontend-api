"""Read-only adapter for API-4A reasoner, audit, and orchestrator artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any

from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import SourceArtifact
from frontend_api.schemas.operations import (
    AuditCycleResponse,
    BacktestDetailResponse,
    BacktestListResponse,
    OrchestratorRunDetailResponse,
    OrchestratorRunsResponse,
    ReadDetailResponse,
    ReadListResponse,
    ReasonerProvidersResponse,
    ReasonerResultsResponse,
    ReplayCycleResponse,
)

_REASONER_ARTIFACT_ROOT = ("reasoner-runtime", "artifacts", "frontend-api")
_AUDIT_ARTIFACT_ROOT = ("audit-eval", "artifacts", "frontend-api")
_ORCHESTRATOR_ARTIFACT_ROOT = ("orchestrator", "artifacts", "frontend-api")
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_STATUS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class OperationsReadAdapter:
    """Read API-4A artifacts without importing owning module implementations."""

    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.reasoner_root = self.project_root.joinpath(*_REASONER_ARTIFACT_ROOT)
        self.audit_root = self.project_root.joinpath(*_AUDIT_ARTIFACT_ROOT)
        self.orchestrator_root = self.project_root.joinpath(
            *_ORCHESTRATOR_ARTIFACT_ROOT
        )

    def list_reasoner_providers(self) -> ReasonerProvidersResponse:
        path = self.reasoner_root / "providers.json"
        return ReasonerProvidersResponse(
            **self._list_payload(
                path,
                source_kind="reasoner_providers",
                unavailable_message="reasoner-runtime providers artifact source unavailable",
                source_unavailable_code="PROJECT_ULT_REASONER_SOURCE_UNAVAILABLE",
                schema_invalid_code="PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
                limit=None,
                cursor=None,
            ).model_dump()
        )

    def list_reasoner_results(
        self,
        *,
        limit: int,
        cursor: str | None,
        cycle_id: str | None,
    ) -> ReasonerResultsResponse:
        validated_cycle_id = self._validate_optional_token(cycle_id, "cycle_id")
        path = self.reasoner_root / "results.json"
        return ReasonerResultsResponse(
            **self._list_payload(
                path,
                source_kind="reasoner_results",
                unavailable_message="reasoner-runtime results artifact source unavailable",
                source_unavailable_code="PROJECT_ULT_REASONER_SOURCE_UNAVAILABLE",
                schema_invalid_code="PROJECT_ULT_REASONER_ARTIFACT_SCHEMA_INVALID",
                limit=limit,
                cursor=cursor,
                filters={"cycle_id": validated_cycle_id}
                if validated_cycle_id is not None
                else None,
            ).model_dump()
        )

    def get_audit(self, cycle_id: str) -> AuditCycleResponse:
        validated_cycle_id = self._validate_token(cycle_id, "cycle_id")
        path = self.audit_root / "audit" / f"{validated_cycle_id}.json"
        return AuditCycleResponse(
            **self._detail_payload(
                path,
                source_kind="audit_cycle",
                source_unavailable_code="PROJECT_ULT_AUDIT_SOURCE_UNAVAILABLE",
                not_found_code="PROJECT_ULT_AUDIT_NOT_FOUND",
                schema_invalid_code="PROJECT_ULT_AUDIT_ARTIFACT_SCHEMA_INVALID",
                label="audit artifact",
                missing_id={"cycle_id": validated_cycle_id},
            ).model_dump()
        )

    def get_replay(self, cycle_id: str) -> ReplayCycleResponse:
        validated_cycle_id = self._validate_token(cycle_id, "cycle_id")
        path = self.audit_root / "replay" / f"{validated_cycle_id}.json"
        return ReplayCycleResponse(
            **self._detail_payload(
                path,
                source_kind="replay_cycle",
                source_unavailable_code="PROJECT_ULT_REPLAY_SOURCE_UNAVAILABLE",
                not_found_code="PROJECT_ULT_REPLAY_NOT_FOUND",
                schema_invalid_code="PROJECT_ULT_REPLAY_ARTIFACT_SCHEMA_INVALID",
                label="replay artifact",
                missing_id={"cycle_id": validated_cycle_id},
            ).model_dump()
        )

    def list_backtests(self, *, limit: int, cursor: str | None) -> BacktestListResponse:
        path = self.audit_root / "backtests.json"
        return BacktestListResponse(
            **self._list_payload(
                path,
                source_kind="backtests",
                unavailable_message="audit-eval backtests artifact source unavailable",
                source_unavailable_code="PROJECT_ULT_BACKTEST_SOURCE_UNAVAILABLE",
                schema_invalid_code="PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
                limit=limit,
                cursor=cursor,
            ).model_dump()
        )

    def get_backtest(self, backtest_id: str) -> BacktestDetailResponse:
        validated_backtest_id = self._validate_token(backtest_id, "backtest_id")
        path = self.audit_root / "backtests" / f"{validated_backtest_id}.json"
        return BacktestDetailResponse(
            **self._detail_payload(
                path,
                source_kind="backtest_detail",
                source_unavailable_code="PROJECT_ULT_BACKTEST_SOURCE_UNAVAILABLE",
                not_found_code="PROJECT_ULT_BACKTEST_NOT_FOUND",
                schema_invalid_code="PROJECT_ULT_BACKTEST_ARTIFACT_SCHEMA_INVALID",
                label="backtest artifact",
                missing_id={"backtest_id": validated_backtest_id},
            ).model_dump()
        )

    def list_orchestrator_runs(
        self,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
    ) -> OrchestratorRunsResponse:
        validated_status = self._validate_status(status)
        path = self.orchestrator_root / "runs.json"
        return OrchestratorRunsResponse(
            **self._list_payload(
                path,
                source_kind="orchestrator_runs",
                unavailable_message="orchestrator runs artifact source unavailable",
                source_unavailable_code="PROJECT_ULT_ORCHESTRATOR_SOURCE_UNAVAILABLE",
                schema_invalid_code="PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
                limit=limit,
                cursor=cursor,
                filters={"status": validated_status}
                if validated_status is not None
                else None,
            ).model_dump()
        )

    def get_orchestrator_run(self, run_id: str) -> OrchestratorRunDetailResponse:
        validated_run_id = self._validate_token(run_id, "run_id")
        path = self.orchestrator_root / "runs" / f"{validated_run_id}.json"
        return OrchestratorRunDetailResponse(
            **self._detail_payload(
                path,
                source_kind="orchestrator_run_detail",
                source_unavailable_code="PROJECT_ULT_ORCHESTRATOR_SOURCE_UNAVAILABLE",
                not_found_code="PROJECT_ULT_ORCHESTRATOR_RUN_NOT_FOUND",
                schema_invalid_code="PROJECT_ULT_ORCHESTRATOR_ARTIFACT_SCHEMA_INVALID",
                label="orchestrator run artifact",
                missing_id={"run_id": validated_run_id},
            ).model_dump()
        )

    def _list_payload(
        self,
        path: Path,
        *,
        source_kind: str,
        unavailable_message: str,
        source_unavailable_code: str,
        schema_invalid_code: str,
        limit: int | None,
        cursor: str | None,
        filters: dict[str, str] | None = None,
    ) -> ReadListResponse:
        offset = self._parse_cursor(cursor)
        if not path.exists():
            return ReadListResponse(
                source_status="unavailable",
                source=self._unavailable_source(source_kind, path, unavailable_message),
                items=[],
                total=0,
                next_cursor=None,
                message=unavailable_message,
            )

        raw = self._load_mapping(
            path,
            source_unavailable_code=source_unavailable_code,
            schema_invalid_code=schema_invalid_code,
        )
        items = self._required_object_list(
            raw,
            path=path,
            schema_invalid_code=schema_invalid_code,
        )
        if filters:
            items = [
                item
                for item in items
                if all(str(item.get(key)) == value for key, value in filters.items())
            ]
        if limit is None:
            page = items[offset:]
        else:
            page = items[offset : offset + limit]
        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(items) else None
        return ReadListResponse(
            source_status="available",
            source=self._artifact_source(source_kind, path),
            items=page,
            total=len(items),
            next_cursor=next_cursor,
        )

    def _detail_payload(
        self,
        path: Path,
        *,
        source_kind: str,
        source_unavailable_code: str,
        not_found_code: str,
        schema_invalid_code: str,
        label: str,
        missing_id: dict[str, str],
    ) -> ReadDetailResponse:
        if not path.parent.exists():
            raise ProjectUltApiError(
                source_unavailable_code,
                f"{label} source unavailable",
                status_code=503,
                details={"path": str(path.parent), **missing_id},
            )
        if not path.exists():
            raise ProjectUltApiError(
                not_found_code,
                f"{label} not found",
                status_code=404,
                details={"path": str(path), **missing_id},
            )

        payload = self._load_mapping(
            path,
            source_unavailable_code=source_unavailable_code,
            schema_invalid_code=schema_invalid_code,
        )
        raw_metadata = payload.get("metadata", {})
        if not isinstance(raw_metadata, Mapping):
            self._raise_schema_error(
                schema_invalid_code,
                f"{label} metadata must be an object",
                path=path,
                details={"actual_type": type(raw_metadata).__name__},
            )
        return ReadDetailResponse(
            source_status="available",
            source=self._artifact_source(source_kind, path),
            payload=dict(payload),
            metadata=dict(raw_metadata),
        )

    def _load_mapping(
        self,
        path: Path,
        *,
        source_unavailable_code: str,
        schema_invalid_code: str,
    ) -> Mapping[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectUltApiError(
                schema_invalid_code,
                "Invalid JSON artifact",
                status_code=500,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise ProjectUltApiError(
                source_unavailable_code,
                "Cannot read artifact",
                status_code=503,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        if not isinstance(raw, Mapping):
            self._raise_schema_error(
                schema_invalid_code,
                "artifact root must be an object",
                path=path,
                details={"actual_type": type(raw).__name__},
            )
        return raw

    def _required_object_list(
        self,
        raw: Mapping[str, Any],
        *,
        path: Path,
        schema_invalid_code: str,
    ) -> list[dict[str, Any]]:
        raw_items = raw.get("items")
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            self._raise_schema_error(
                schema_invalid_code,
                "artifact items must be a list",
                path=path,
                details={"actual_type": type(raw_items).__name__},
            )
        items: list[dict[str, Any]] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, Mapping):
                self._raise_schema_error(
                    schema_invalid_code,
                    "artifact item must be an object",
                    path=path,
                    details={"index": index, "actual_type": type(item).__name__},
                )
            items.append(dict(item))
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, Mapping):
            self._raise_schema_error(
                schema_invalid_code,
                "artifact metadata must be an object",
                path=path,
                details={"actual_type": type(metadata).__name__},
            )
        return items

    def _parse_cursor(self, cursor: str | None) -> int:
        if cursor in (None, ""):
            return 0
        try:
            offset = int(cursor)
        except ValueError as exc:
            raise ProjectUltApiError(
                "PROJECT_ULT_CURSOR_INVALID",
                "cursor must be a non-negative integer offset",
                status_code=400,
                details={"cursor": cursor},
            ) from exc
        if offset < 0:
            raise ProjectUltApiError(
                "PROJECT_ULT_CURSOR_INVALID",
                "cursor must be a non-negative integer offset",
                status_code=400,
                details={"cursor": cursor},
            )
        return offset

    def _validate_optional_token(self, value: str | None, field_name: str) -> str | None:
        if value in (None, ""):
            return None
        return self._validate_token(str(value), field_name)

    def _validate_token(self, value: str, field_name: str) -> str:
        if value and _SAFE_TOKEN_PATTERN.fullmatch(value):
            return value
        raise ProjectUltApiError(
            "PROJECT_ULT_IDENTIFIER_INVALID",
            f"{field_name} must be a non-empty artifact-safe identifier",
            status_code=400,
            details={field_name: value},
        )

    def _validate_status(self, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if _STATUS_PATTERN.fullmatch(value):
            return value
        raise ProjectUltApiError(
            "PROJECT_ULT_STATUS_INVALID",
            "status must be a valid status identifier",
            status_code=400,
            details={"status": value},
        )

    def _raise_schema_error(
        self,
        code: str,
        message: str,
        *,
        path: Path,
        details: dict[str, Any] | None = None,
    ) -> None:
        raise ProjectUltApiError(
            code,
            message,
            status_code=500,
            details={"path": str(path), **(details or {})},
        )

    def _artifact_source(self, kind: str, path: Path) -> SourceArtifact:
        return SourceArtifact(kind=kind, path=str(path), exists=True)

    def _unavailable_source(
        self,
        kind: str,
        path: Path,
        message: str,
    ) -> SourceArtifact:
        return SourceArtifact(
            kind=kind,
            path=str(path),
            exists=False,
            message=message,
        )
