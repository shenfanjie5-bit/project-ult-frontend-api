"""Read-only adapters for API-3A entity and data artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import SourceArtifact
from frontend_api.schemas.entity_data import (
    DataRowsResponse,
    EntityProfileResponse,
    EntitySearchItem,
    EntitySearchResponse,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

_ENTITY_ARTIFACT_ROOT = ("entity-registry", "artifacts", "frontend-api")
_DATA_ARTIFACT_ROOT = ("data-platform", "artifacts", "frontend-api", "data")
_DATA_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EntityDataReadAdapter:
    """Read entity-registry and data-platform frontend-api artifacts."""

    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.entity_artifact_root = self.project_root.joinpath(*_ENTITY_ARTIFACT_ROOT)
        self.data_artifact_root = self.project_root.joinpath(*_DATA_ARTIFACT_ROOT)

    def search_entities(
        self,
        *,
        query: str | None,
        limit: int,
        cursor: str | None = None,
    ) -> EntitySearchResponse:
        path = self.entity_artifact_root / "entities.json"
        offset = self._parse_cursor(cursor)
        if not path.exists():
            return EntitySearchResponse(
                source_status="unavailable",
                source=self._unavailable_source(
                    "entity_index",
                    path,
                    "entity-registry frontend-api entity artifact not found",
                ),
                total=0,
                next_cursor=None,
                items=[],
                message="entity-registry entity artifact source unavailable",
            )

        items = self._load_entity_items(path)
        filtered = self._filter_entities(items, query)
        page = filtered[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(filtered) else None
        return EntitySearchResponse(
            source_status="available",
            source=self._artifact_source("entity_index", path),
            total=len(filtered),
            next_cursor=next_cursor,
            items=page,
        )

    def get_entity_profile(self, entity_id: str) -> EntityProfileResponse:
        self._validate_entity_id(entity_id)
        path = self.entity_artifact_root / "entities.json"
        if not path.exists():
            raise ProjectUltApiError(
                "PROJECT_ULT_ENTITY_SOURCE_UNAVAILABLE",
                "entity-registry frontend-api entity artifact not found",
                status_code=503,
                details={"path": str(path), "entity_id": entity_id},
            )

        raw_items = self._load_entity_raw_items(path)
        for raw_item in raw_items:
            if str(raw_item.get("entity_id")) == entity_id:
                profile = raw_item.get("profile")
                if not isinstance(profile, Mapping):
                    self._raise_schema_error(
                        "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
                        "entity profile must be an object",
                        path=path,
                        details={"entity_id": entity_id},
                    )
                return EntityProfileResponse(
                    source_status="available",
                    source=self._artifact_source("entity_profile", path),
                    entity_id=entity_id,
                    profile=dict(profile),
                )

        raise ProjectUltApiError(
            "PROJECT_ULT_ENTITY_NOT_FOUND",
            f"Entity not found: {entity_id}",
            status_code=404,
            details={"path": str(path), "entity_id": entity_id},
        )

    def read_canonical_table(
        self,
        table: str,
        *,
        limit: int,
        cursor: str | None,
    ) -> DataRowsResponse:
        validated_table = self._validate_data_id(table, "table")
        path = self.data_artifact_root / "canonical" / f"{validated_table}.json"
        return self._read_data_rows(
            path,
            kind="canonical_table",
            table=validated_table,
            source_name=None,
            limit=limit,
            cursor=cursor,
            unavailable_message="data-platform canonical artifact source unavailable",
        )

    def read_raw_source(
        self,
        source: str,
        *,
        limit: int,
        cursor: str | None,
    ) -> DataRowsResponse:
        validated_source = self._validate_data_id(source, "source")
        path = self.data_artifact_root / "raw" / f"{validated_source}.json"
        return self._read_data_rows(
            path,
            kind="raw_source",
            table=None,
            source_name=validated_source,
            limit=limit,
            cursor=cursor,
            unavailable_message="data-platform raw artifact source unavailable",
        )

    def _read_data_rows(
        self,
        path: Path,
        *,
        kind: str,
        table: str | None,
        source_name: str | None,
        limit: int,
        cursor: str | None,
        unavailable_message: str,
    ) -> DataRowsResponse:
        offset = self._parse_cursor(cursor)
        if not path.exists():
            return DataRowsResponse(
                source_status="unavailable",
                source=self._unavailable_source(kind, path, unavailable_message),
                table=table,
                source_name=source_name,
                columns=[],
                total=0,
                next_cursor=None,
                items=[],
                message=unavailable_message,
            )

        raw = self._load_json(
            path,
            unavailable_code="PROJECT_ULT_DATA_ARTIFACT_UNAVAILABLE",
            invalid_code="PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID",
        )
        if not isinstance(raw, Mapping):
            self._raise_schema_error(
                "PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID",
                "data artifact root must be an object",
                path=path,
                details={"actual_type": type(raw).__name__},
            )
        items = raw.get("items")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            self._raise_schema_error(
                "PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID",
                "data artifact items must be a list",
                path=path,
                details={"actual_type": type(items).__name__},
            )
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                self._raise_schema_error(
                    "PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID",
                    "data artifact item must be an object",
                    path=path,
                    details={"index": index, "actual_type": type(item).__name__},
                )
            rows.append(dict(item))

        raw_columns = raw.get("columns")
        if raw_columns is None:
            columns = list(rows[0]) if rows else []
        elif (
            isinstance(raw_columns, Sequence)
            and not isinstance(raw_columns, (str, bytes))
            and all(isinstance(column, str) for column in raw_columns)
        ):
            columns = list(raw_columns)
        else:
            self._raise_schema_error(
                "PROJECT_ULT_DATA_ARTIFACT_SCHEMA_INVALID",
                "data artifact columns must be a string list",
                path=path,
                details={"actual_type": type(raw_columns).__name__},
            )

        page = rows[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(rows) else None
        return DataRowsResponse(
            source_status="available",
            source=self._artifact_source(kind, path),
            table=table,
            source_name=source_name,
            columns=columns,
            total=len(rows),
            next_cursor=next_cursor,
            items=page,
        )

    def _load_entity_items(self, path: Path) -> list[EntitySearchItem]:
        raw_items = self._load_entity_raw_items(path)
        return [
            self._entity_search_item(raw_item, path=path, index=index)
            for index, raw_item in enumerate(raw_items)
        ]

    def _load_entity_raw_items(self, path: Path) -> list[dict[str, Any]]:
        raw = self._load_json(
            path,
            unavailable_code="PROJECT_ULT_ENTITY_ARTIFACT_UNAVAILABLE",
            invalid_code="PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
        )
        if not isinstance(raw, Mapping):
            self._raise_schema_error(
                "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
                "entity artifact root must be an object",
                path=path,
                details={"actual_type": type(raw).__name__},
            )
        raw_items = raw.get("items")
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            self._raise_schema_error(
                "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
                "entity artifact items must be a list",
                path=path,
                details={"actual_type": type(raw_items).__name__},
            )
        items: list[dict[str, Any]] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, Mapping):
                self._raise_schema_error(
                    "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
                    "entity artifact item must be an object",
                    path=path,
                    details={"index": index, "actual_type": type(item).__name__},
                )
            items.append(dict(item))
        return items

    def _entity_search_item(
        self,
        raw: Mapping[str, Any],
        *,
        path: Path,
        index: int,
    ) -> EntitySearchItem:
        metadata = raw.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            self._raise_schema_error(
                "PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
                "entity search item metadata must be an object",
                path=path,
                details={"index": index, "actual_type": type(metadata).__name__},
            )
        payload = {
            "entity_id": raw.get("entity_id"),
            "display_name": raw.get("display_name"),
            "entity_type": raw.get("entity_type"),
            "aliases": raw.get("aliases", []),
            "score": raw.get("score"),
            "metadata": dict(metadata) if isinstance(metadata, Mapping) else {},
        }
        return self._validate_model(
            EntitySearchItem,
            payload,
            code="PROJECT_ULT_ENTITY_ARTIFACT_SCHEMA_INVALID",
            label="entity search item",
            path=path,
            index=index,
        )

    def _filter_entities(
        self,
        items: list[EntitySearchItem],
        query: str | None,
    ) -> list[EntitySearchItem]:
        normalized_query = (query or "").strip().casefold()
        if not normalized_query:
            return items
        filtered: list[EntitySearchItem] = []
        for item in items:
            haystack = " ".join(
                [
                    item.entity_id,
                    item.display_name or "",
                    item.entity_type or "",
                    *item.aliases,
                ]
            ).casefold()
            if normalized_query in haystack:
                filtered.append(item)
        return filtered

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

    def _validate_entity_id(self, entity_id: str) -> None:
        if entity_id and "/" not in entity_id and entity_id == entity_id.strip():
            return
        raise ProjectUltApiError(
            "PROJECT_ULT_ENTITY_ID_INVALID",
            "entity_id must be a non-empty path-safe identifier",
            status_code=400,
            details={"entity_id": entity_id},
        )

    def _validate_data_id(self, value: str, field_name: str) -> str:
        if _DATA_ID_PATTERN.fullmatch(value):
            return value
        raise ProjectUltApiError(
            "PROJECT_ULT_DATA_IDENTIFIER_INVALID",
            f"{field_name} must be a valid data artifact identifier",
            status_code=400,
            details={field_name: value},
        )

    def _load_json(
        self,
        path: Path,
        *,
        unavailable_code: str,
        invalid_code: str,
    ) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectUltApiError(
                invalid_code,
                "Invalid JSON artifact",
                status_code=500,
                details={"path": str(path), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise ProjectUltApiError(
                unavailable_code,
                "Cannot read artifact",
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
        path: Path,
        index: int | None = None,
    ) -> ModelT:
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            details: dict[str, Any] = {
                "path": str(path),
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
