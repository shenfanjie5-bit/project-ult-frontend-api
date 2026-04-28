"""Read-only adapter for data-platform cycle/formal public sources.

The adapter never imports data-platform private modules. It first looks for a
small JSON read-model artifact set, then optionally calls data-platform public
packages if they are installed in the current runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import importlib
import json
from pathlib import Path
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import SourceArtifact
from frontend_api.schemas.cycle import (
    CycleListResponse,
    CycleRecord,
    FormalObjectResponse,
    ManifestResponse,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

_ARTIFACT_ROOT = ("data-platform", "artifacts", "frontend-api")
_CYCLE_ID_PATTERN = re.compile(r"^CYCLE_\d{8}$")
_FORMAL_OBJECT_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NOT_FOUND_ERROR_NAMES = frozenset(
    {
        "CycleNotFound",
        "PublishManifestNotFound",
        "FormalManifestNotFound",
        "FormalSnapshotNotPublished",
        "FormalTableSnapshotNotFound",
    }
)
_INVALID_INPUT_ERROR_NAMES = frozenset(
    {
        "InvalidCycleId",
        "FormalObjectTypeInvalid",
    }
)
_SOURCE_SCHEMA_ERROR_NAMES = frozenset({"InvalidFormalSnapshotManifest"})


class DataPlatformReadAdapter:
    """Read cycle, formal object, and manifest data from stable public sources."""

    def __init__(
        self,
        *,
        project_root: Path,
        allow_public_api_fallback: bool = False,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.artifact_root = self.project_root.joinpath(*_ARTIFACT_ROOT)
        self.allow_public_api_fallback = allow_public_api_fallback

    def list_cycles(self) -> CycleListResponse:
        index_path = self.artifact_root / "cycles.json"
        if index_path.exists():
            raw = self._load_json(
                index_path,
                code="PROJECT_ULT_CYCLE_ARTIFACT_UNAVAILABLE",
                label="data-platform cycle index",
            )
            items = self._cycle_items_from_index(raw, index_path)
            return CycleListResponse(
                source_status="available",
                source=self._artifact_source("cycle_index", index_path),
                total=len(items),
                items=items,
            )

        fn, reason = self._load_public_callable("data_platform.cycle", "list_cycles")
        if fn is not None:
            source = self._public_source("data_platform.cycle", "list_cycles")
            try:
                raw_result = fn()
            except Exception as exc:  # pragma: no cover - depends on local infra
                message = f"data-platform public list_cycles unavailable: {exc}"
                return CycleListResponse(
                    source_status="unavailable",
                    source=self._unavailable_source("cycle_index", index_path, message),
                    total=0,
                    items=[],
                    message=message,
                )
            raw_items = self._jsonable(raw_result)
            if not isinstance(raw_items, Sequence) or isinstance(
                raw_items,
                (str, bytes),
            ):
                raise ProjectUltApiError(
                    "PROJECT_ULT_CYCLE_SOURCE_SCHEMA_INVALID",
                    "Invalid data-platform public cycle list: result must be a list",
                    status_code=500,
                    details={
                        "public_api": source.path,
                        "actual_type": type(raw_items).__name__,
                    },
                )
            items = [
                self._cycle_record_from_payload(
                    item,
                    path=source.path,
                    index=index,
                    schema_code="PROJECT_ULT_CYCLE_SOURCE_SCHEMA_INVALID",
                )
                for index, item in enumerate(raw_items)
            ]
            return CycleListResponse(
                source_status="available",
                source=source,
                total=len(items),
                items=items,
            )

        message = self._missing_cycle_source_message(reason)
        return CycleListResponse(
            source_status="unavailable",
            source=self._unavailable_source("cycle_index", index_path, message),
            total=0,
            items=[],
            message=message,
        )

    def get_cycle(self, cycle_id: str) -> CycleRecord:
        self._validate_cycle_id(cycle_id)
        detail_path = self.artifact_root / "cycles" / f"{cycle_id}.json"
        if detail_path.exists():
            raw = self._load_json(
                detail_path,
                code="PROJECT_ULT_CYCLE_ARTIFACT_UNAVAILABLE",
                label=f"data-platform cycle detail {cycle_id}",
            )
            return self._cycle_record_from_payload(raw, path=str(detail_path))

        index_path = self.artifact_root / "cycles.json"
        if index_path.exists():
            items = self._cycle_items_from_index(
                self._load_json(
                    index_path,
                    code="PROJECT_ULT_CYCLE_ARTIFACT_UNAVAILABLE",
                    label="data-platform cycle index",
                ),
                index_path,
            )
            for item in items:
                if item.cycle_id == cycle_id:
                    return item
            raise ProjectUltApiError(
                "PROJECT_ULT_CYCLE_NOT_FOUND",
                f"Cycle not found: {cycle_id}",
                status_code=404,
                details={"cycle_id": cycle_id, "path": str(index_path)},
            )

        fn, reason = self._load_public_callable("data_platform.cycle", "get_cycle")
        if fn is None:
            self._raise_source_unavailable(
                "PROJECT_ULT_CYCLE_SOURCE_UNAVAILABLE",
                "No data-platform public cycle source is available",
                artifact_path=detail_path,
                public_api="data_platform.cycle:get_cycle",
                reason=reason,
            )
        try:
            raw_cycle = fn(cycle_id)
        except Exception as exc:
            self._raise_public_exception(
                exc,
                not_found_code="PROJECT_ULT_CYCLE_NOT_FOUND",
                invalid_code="PROJECT_ULT_CYCLE_ID_INVALID",
                schema_code="PROJECT_ULT_CYCLE_SOURCE_SCHEMA_INVALID",
                unavailable_code="PROJECT_ULT_CYCLE_SOURCE_UNAVAILABLE",
                public_api="data_platform.cycle:get_cycle",
                details={"cycle_id": cycle_id},
            )
        return self._cycle_record_from_payload(
            self._jsonable(raw_cycle),
            path="data_platform.cycle:get_cycle",
            schema_code="PROJECT_ULT_CYCLE_SOURCE_SCHEMA_INVALID",
        )

    def get_formal_object(
        self,
        object_type: str,
        *,
        cycle_id: str | None = None,
    ) -> FormalObjectResponse:
        validated_object_type = self._validate_formal_object_type(object_type)
        if cycle_id is not None:
            self._validate_cycle_id(cycle_id)

        artifact_path = self._formal_artifact_path(validated_object_type, cycle_id)
        if artifact_path.exists():
            raw = self._load_json(
                artifact_path,
                code="PROJECT_ULT_FORMAL_ARTIFACT_UNAVAILABLE",
                label=f"data-platform formal object {validated_object_type}",
            )
            return self._formal_response_from_payload(
                raw,
                object_type=validated_object_type,
                cycle_id=cycle_id,
                source=self._artifact_source("formal_object", artifact_path),
            )

        formal_dir = self.artifact_root / "formal"
        if formal_dir.exists():
            raise ProjectUltApiError(
                "PROJECT_ULT_FORMAL_OBJECT_NOT_FOUND",
                "Formal object artifact not found",
                status_code=404,
                details={
                    "object_type": validated_object_type,
                    "cycle_id": cycle_id,
                    "path": str(artifact_path),
                },
            )

        public_api = (
            "data_platform.serving:get_formal_by_id"
            if cycle_id is not None
            else "data_platform.serving:get_formal_latest"
        )
        fn_name = "get_formal_by_id" if cycle_id is not None else "get_formal_latest"
        fn, reason = self._load_public_callable("data_platform.serving", fn_name)
        if fn is None:
            self._raise_source_unavailable(
                "PROJECT_ULT_FORMAL_SOURCE_UNAVAILABLE",
                "No data-platform public formal source is available",
                artifact_path=artifact_path,
                public_api=public_api,
                reason=reason,
            )

        try:
            raw_object = (
                fn(cycle_id, validated_object_type)
                if cycle_id is not None
                else fn(validated_object_type)
            )
            return self._formal_response_from_payload(
                self._jsonable(raw_object),
                object_type=validated_object_type,
                cycle_id=cycle_id,
                source=self._public_source("data_platform.serving", fn_name),
                schema_code="PROJECT_ULT_FORMAL_SOURCE_SCHEMA_INVALID",
            )
        except Exception as exc:
            self._raise_public_exception(
                exc,
                not_found_code="PROJECT_ULT_FORMAL_OBJECT_NOT_FOUND",
                invalid_code="PROJECT_ULT_FORMAL_OBJECT_TYPE_INVALID",
                schema_code="PROJECT_ULT_FORMAL_SOURCE_SCHEMA_INVALID",
                unavailable_code="PROJECT_ULT_FORMAL_SOURCE_UNAVAILABLE",
                public_api=public_api,
                details={"object_type": validated_object_type, "cycle_id": cycle_id},
            )

    def get_latest_manifest(self) -> ManifestResponse:
        artifact_path = self.artifact_root / "manifests" / "latest.json"
        if artifact_path.exists():
            raw = self._load_json(
                artifact_path,
                code="PROJECT_ULT_MANIFEST_ARTIFACT_UNAVAILABLE",
                label="data-platform latest manifest",
            )
            return self._manifest_response_from_payload(
                raw,
                source=self._artifact_source("latest_manifest", artifact_path),
            )

        fn, reason = self._load_public_callable(
            "data_platform.cycle",
            "get_latest_publish_manifest",
        )
        if fn is None:
            self._raise_source_unavailable(
                "PROJECT_ULT_MANIFEST_SOURCE_UNAVAILABLE",
                "No data-platform public manifest source is available",
                artifact_path=artifact_path,
                public_api="data_platform.cycle:get_latest_publish_manifest",
                reason=reason,
            )
        try:
            return self._manifest_response_from_payload(
                self._jsonable(fn()),
                source=self._public_source(
                    "data_platform.cycle",
                    "get_latest_publish_manifest",
                ),
                schema_code="PROJECT_ULT_MANIFEST_SOURCE_SCHEMA_INVALID",
            )
        except Exception as exc:
            self._raise_public_exception(
                exc,
                not_found_code="PROJECT_ULT_MANIFEST_NOT_FOUND",
                invalid_code="PROJECT_ULT_MANIFEST_SCHEMA_INVALID",
                schema_code="PROJECT_ULT_MANIFEST_SOURCE_SCHEMA_INVALID",
                unavailable_code="PROJECT_ULT_MANIFEST_SOURCE_UNAVAILABLE",
                public_api="data_platform.cycle:get_latest_publish_manifest",
                details={},
            )

    def _cycle_items_from_index(self, raw: Any, path: Path) -> list[CycleRecord]:
        normalized = self._jsonable(raw)
        if isinstance(normalized, Mapping):
            raw_items = normalized.get("items", normalized.get("cycles"))
        else:
            raw_items = normalized
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raise ProjectUltApiError(
                "PROJECT_ULT_CYCLE_ARTIFACT_SCHEMA_INVALID",
                "Invalid data-platform cycle index: items must be a list",
                status_code=500,
                details={"path": str(path), "actual_type": type(raw_items).__name__},
            )
        return [
            self._cycle_record_from_payload(item, path=str(path), index=index)
            for index, item in enumerate(raw_items)
        ]

    def _cycle_record_from_payload(
        self,
        raw: Any,
        *,
        path: str,
        index: int | None = None,
        schema_code: str = "PROJECT_ULT_CYCLE_ARTIFACT_SCHEMA_INVALID",
    ) -> CycleRecord:
        normalized = self._jsonable(raw)
        if not isinstance(normalized, Mapping):
            self._raise_artifact_schema_error(
                schema_code,
                "data-platform cycle record",
                path=path,
                index=index,
                actual_type=type(normalized).__name__,
            )

        payload = dict(normalized)
        if "cycle_id" not in payload and "published_cycle_id" in payload:
            payload["cycle_id"] = payload["published_cycle_id"]

        known_fields = {
            "cycle_id",
            "status",
            "cycle_date",
            "cutoff_submitted_at",
            "cutoff_ingest_seq",
            "candidate_count",
            "selection_frozen_at",
            "created_at",
            "updated_at",
            "manifest",
            "metadata",
        }
        metadata = {
            str(key): value
            for key, value in payload.items()
            if key not in known_fields
        }
        if isinstance(payload.get("metadata"), Mapping):
            metadata.update(dict(payload["metadata"]))
        record_payload = {
            key: payload.get(key)
            for key in known_fields
            if key in payload and key != "metadata"
        }
        record_payload["metadata"] = metadata
        return self._validate_model(
            CycleRecord,
            record_payload,
            code=schema_code,
            label="data-platform cycle record",
            path=path,
            index=index,
        )

    def _formal_response_from_payload(
        self,
        raw: Any,
        *,
        object_type: str,
        cycle_id: str | None,
        source: SourceArtifact,
        schema_code: str = "PROJECT_ULT_FORMAL_ARTIFACT_SCHEMA_INVALID",
    ) -> FormalObjectResponse:
        normalized = self._jsonable(raw)
        if isinstance(normalized, Mapping):
            raw_mapping = dict(normalized)
            response_object_type = str(
                raw_mapping.get(
                    "object_type",
                    raw_mapping.get("object_name", object_type),
                )
            )
            response_cycle_id = raw_mapping.get("cycle_id", cycle_id)
            snapshot_id = raw_mapping.get("snapshot_id")
            payload = raw_mapping.get("payload", normalized)
            metadata = self._metadata_from_mapping(
                raw_mapping,
                {
                    "object_type",
                    "object_name",
                    "cycle_id",
                    "snapshot_id",
                    "payload",
                    "metadata",
                },
            )
        else:
            response_object_type = object_type
            response_cycle_id = cycle_id
            snapshot_id = None
            payload = normalized
            metadata = {}

        return self._validate_model(
            FormalObjectResponse,
            {
                "object_type": response_object_type,
                "cycle_id": response_cycle_id,
                "source_status": "available",
                "source": source.model_dump(mode="json"),
                "snapshot_id": snapshot_id,
                "payload": payload,
                "metadata": metadata,
            },
            code=schema_code,
            label="data-platform formal object",
            path=source.path,
        )

    def _manifest_response_from_payload(
        self,
        raw: Any,
        *,
        source: SourceArtifact,
        schema_code: str = "PROJECT_ULT_MANIFEST_ARTIFACT_SCHEMA_INVALID",
    ) -> ManifestResponse:
        normalized = self._jsonable(raw)
        if not isinstance(normalized, Mapping):
            self._raise_artifact_schema_error(
                schema_code,
                "data-platform latest manifest",
                path=source.path,
                actual_type=type(normalized).__name__,
            )

        raw_mapping = dict(normalized)
        snapshots = raw_mapping.get(
            "formal_table_snapshots",
            raw_mapping.get("table_snapshots", {}),
        )
        if not isinstance(snapshots, Mapping):
            snapshots = {}
        return self._validate_model(
            ManifestResponse,
            {
                "source_status": "available",
                "source": source.model_dump(mode="json"),
                "cycle_id": raw_mapping.get(
                    "cycle_id",
                    raw_mapping.get("published_cycle_id"),
                ),
                "manifest_ref": raw_mapping.get("manifest_ref"),
                "published_at": raw_mapping.get("published_at"),
                "formal_table_snapshots": dict(snapshots),
                "payload": raw_mapping.get("payload", normalized),
                "metadata": self._metadata_from_mapping(
                    raw_mapping,
                    {
                        "cycle_id",
                        "published_cycle_id",
                        "manifest_ref",
                        "published_at",
                        "formal_table_snapshots",
                        "table_snapshots",
                        "payload",
                        "metadata",
                    },
                ),
            },
            code=schema_code,
            label="data-platform latest manifest",
            path=source.path,
        )

    def _formal_artifact_path(self, object_type: str, cycle_id: str | None) -> Path:
        name = "latest" if cycle_id is None else cycle_id
        return self.artifact_root / "formal" / object_type / f"{name}.json"

    def _load_json(self, path: Path, *, code: str, label: str) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise ProjectUltApiError(
                code,
                f"Invalid JSON in {label}",
                status_code=500,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise ProjectUltApiError(
                code,
                f"Cannot read {label}",
                status_code=503,
                details={"path": str(path), "error": str(exc)},
            ) from exc

    def _validate_model(
        self,
        model_type: type[ModelT],
        payload: dict[str, Any],
        *,
        code: str,
        label: str,
        path: str,
        index: int | None = None,
    ) -> ModelT:
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            details: dict[str, Any] = {
                "path": path,
                "errors": exc.errors(include_url=False),
            }
            if index is not None:
                details["index"] = index
            raise ProjectUltApiError(
                code,
                f"Invalid {label}: schema validation failed",
                status_code=500,
                details=details,
            ) from exc

    def _validate_cycle_id(self, cycle_id: str) -> None:
        if _CYCLE_ID_PATTERN.fullmatch(cycle_id):
            return
        raise ProjectUltApiError(
            "PROJECT_ULT_CYCLE_ID_INVALID",
            "cycle_id must match CYCLE_YYYYMMDD",
            status_code=400,
            details={"cycle_id": cycle_id},
        )

    def _validate_formal_object_type(self, object_type: str) -> str:
        if _FORMAL_OBJECT_TYPE_PATTERN.fullmatch(object_type):
            return object_type
        raise ProjectUltApiError(
            "PROJECT_ULT_FORMAL_OBJECT_TYPE_INVALID",
            "object_type must be a valid formal object identifier",
            status_code=400,
            details={"object_type": object_type},
        )

    def _load_public_callable(
        self,
        module_name: str,
        attr_name: str,
    ) -> tuple[Callable[..., Any] | None, str | None]:
        if not self.allow_public_api_fallback:
            return None, "data-platform public API fallback disabled"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - runtime optional dependency
            return None, f"{module_name} unavailable: {type(exc).__name__}: {exc}"
        candidate = getattr(module, attr_name, None)
        if callable(candidate):
            return candidate, None
        return None, f"{module_name}:{attr_name} is not callable"

    def _raise_public_exception(
        self,
        exc: Exception,
        *,
        not_found_code: str,
        invalid_code: str,
        schema_code: str,
        unavailable_code: str,
        public_api: str,
        details: dict[str, Any],
    ) -> None:
        if isinstance(exc, ProjectUltApiError):
            raise exc
        error_name = type(exc).__name__
        merged_details = {
            **details,
            "public_api": public_api,
            "error_type": error_name,
            "error": str(exc),
        }
        if error_name in _NOT_FOUND_ERROR_NAMES:
            raise ProjectUltApiError(
                not_found_code,
                str(exc) or "data-platform public object not found",
                status_code=404,
                details=merged_details,
            ) from exc
        if error_name in _INVALID_INPUT_ERROR_NAMES:
            raise ProjectUltApiError(
                invalid_code,
                str(exc) or "invalid data-platform public API input",
                status_code=400,
                details=merged_details,
            ) from exc
        if error_name in _SOURCE_SCHEMA_ERROR_NAMES:
            raise ProjectUltApiError(
                schema_code,
                str(exc) or "invalid data-platform public API source schema",
                status_code=500,
                details=merged_details,
            ) from exc
        raise ProjectUltApiError(
            unavailable_code,
            "data-platform public API failed",
            status_code=503,
            details=merged_details,
        ) from exc

    def _raise_source_unavailable(
        self,
        code: str,
        message: str,
        *,
        artifact_path: Path,
        public_api: str,
        reason: str | None,
    ) -> None:
        raise ProjectUltApiError(
            code,
            message,
            status_code=503,
            details={
                "artifact_path": str(artifact_path),
                "public_api": public_api,
                "reason": reason,
            },
        )

    def _raise_artifact_schema_error(
        self,
        code: str,
        label: str,
        *,
        path: str,
        index: int | None = None,
        actual_type: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"path": path}
        if index is not None:
            details["index"] = index
        if actual_type is not None:
            details["actual_type"] = actual_type
        raise ProjectUltApiError(
            code,
            f"Invalid {label}: schema validation failed",
            status_code=500,
            details=details,
        )

    def _artifact_source(
        self,
        kind: str,
        path: Path,
        *,
        message: str | None = None,
    ) -> SourceArtifact:
        return SourceArtifact(
            kind=kind,
            path=str(path),
            exists=path.exists(),
            message=message,
        )

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

    def _public_source(self, module_name: str, attr_name: str) -> SourceArtifact:
        return SourceArtifact(
            kind="data_platform_public_api",
            path=f"{module_name}:{attr_name}",
            exists=True,
        )

    def _missing_cycle_source_message(self, reason: str | None) -> str:
        expected = self.artifact_root / "cycles.json"
        suffix = f" ({reason})" if reason else ""
        return (
            "No data-platform public cycle list source is available; expected "
            f"{expected} or importable data_platform.cycle:list_cycles{suffix}"
        )

    def _metadata_from_mapping(
        self,
        raw: Mapping[str, Any],
        reserved_keys: set[str],
    ) -> dict[str, Any]:
        metadata = {
            str(key): value
            for key, value in raw.items()
            if key not in reserved_keys
        }
        if isinstance(raw.get("metadata"), Mapping):
            metadata.update(dict(raw["metadata"]))
        return metadata

    def _jsonable(self, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: self._jsonable(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, Mapping):
            return {str(key): self._jsonable(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [self._jsonable(item) for item in value]
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if hasattr(value, "to_pylist") and callable(value.to_pylist):
            rows = value.to_pylist()
            column_names = getattr(value, "column_names", None)
            return {
                "rows": self._jsonable(rows),
                "row_count": len(rows),
                "columns": list(column_names) if column_names is not None else [],
            }
        return value
