"""Read-only adapter over assembly public artifacts.

This module intentionally reads YAML artifacts directly instead of importing
assembly loaders, validators, runners, or sibling module implementations.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from frontend_api import __version__
from frontend_api.errors import ProjectUltApiError
from frontend_api.schemas.common import ServiceIdentity, SourceArtifact
from frontend_api.schemas.system import (
    CompatibilityRecord,
    CompatibilityResponse,
    HealthResponse,
    HealthSummary,
    ModuleRecord,
    ModulesResponse,
    ProfileCompatibilityEvidence,
    ProfileRecord,
    ProfilesResponse,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class AssemblyAdapter:
    """Read assembly registry, profile, and compatibility artifacts."""

    def __init__(
        self,
        *,
        project_root: Path,
        active_profile: str,
        mode: str,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.active_profile = active_profile
        self.mode = mode
        self.assembly_root = self.project_root / "assembly"
        self.registry_path = self.assembly_root / "module-registry.yaml"
        self.profiles_dir = self.assembly_root / "profiles"
        self.compatibility_path = self.assembly_root / "compatibility-matrix.yaml"

    def health(self) -> HealthResponse:
        artifacts = self._artifact_statuses()
        missing = [artifact for artifact in artifacts if not artifact.exists]

        modules = self._try_modules()
        profiles = self._try_profiles()
        compatibility = self._try_compatibility()

        active_profile_found = any(
            profile.profile_id == self.active_profile
            for profile in profiles.items
        )
        active_compat = [
            item
            for item in compatibility.items
            if item.profile_id == self.active_profile and item.status == "verified"
        ]

        degraded_reasons: list[str] = []
        if missing:
            degraded_reasons.append("missing assembly artifacts")
        if not active_profile_found:
            degraded_reasons.append("active profile manifest not found")
        if not active_compat:
            degraded_reasons.append("active profile has no verified compat row")

        status = "degraded" if degraded_reasons else "healthy"
        message = (
            "frontend-api system artifacts are readable"
            if status == "healthy"
            else "; ".join(degraded_reasons)
        )

        return HealthResponse(
            status=status,
            service=ServiceIdentity(
                module_id="frontend-api",
                version=__version__,
                mode=self.mode,
                active_profile=self.active_profile,
            ),
            project_root=str(self.project_root),
            assembly_root=str(self.assembly_root),
            artifacts=artifacts,
            modules=HealthSummary(
                total=modules.total,
                details={"statuses": modules.statuses},
            ),
            profiles=HealthSummary(
                total=profiles.total,
                details={"active_profile_found": active_profile_found},
            ),
            compatibility=HealthSummary(
                total=compatibility.total,
                details={
                    "statuses": compatibility.statuses,
                    "active_verified_rows": len(active_compat),
                },
            ),
            message=message,
        )

    def list_modules(self) -> ModulesResponse:
        raw_items = self._load_yaml_list(
            self.registry_path,
            code="PROJECT_ULT_MODULE_REGISTRY_UNAVAILABLE",
            label="assembly module registry",
        )
        items = [
            self._validate_record(
                ModuleRecord,
                self._normalize_yaml_scalars(item),
                code="PROJECT_ULT_MODULE_REGISTRY_SCHEMA_INVALID",
                label="assembly module registry entry",
                path=self.registry_path,
                index=index,
            )
            for index, item in enumerate(raw_items)
        ]
        statuses = Counter(item.integration_status for item in items)
        return ModulesResponse(
            source_path=str(self.registry_path),
            total=len(items),
            statuses=dict(sorted(statuses.items())),
            items=items,
        )

    def list_profiles(self) -> ProfilesResponse:
        self._ensure_path(
            self.profiles_dir,
            code="PROJECT_ULT_PROFILES_UNAVAILABLE",
            label="assembly profiles directory",
        )
        profile_paths = sorted(
            path
            for path in self.profiles_dir.iterdir()
            if path.suffix in {".yaml", ".yml"}
        )
        compatibility_by_profile = self._default_compatibility_by_profile()
        items: list[ProfileRecord] = []
        for path in profile_paths:
            raw_profile = self._load_yaml_mapping(
                path,
                code="PROJECT_ULT_PROFILE_UNAVAILABLE",
                label=f"profile manifest {path.name}",
            )
            normalized = self._normalize_yaml_scalars(raw_profile)
            profile_id = str(normalized.get("profile_id", path.stem))
            evidence = compatibility_by_profile.get(
                profile_id,
                ProfileCompatibilityEvidence(),
            )
            items.append(
                self._validate_record(
                    ProfileRecord,
                    {
                        **normalized,
                        "compatibility": evidence.model_dump(mode="json"),
                    },
                    code="PROJECT_ULT_PROFILE_SCHEMA_INVALID",
                    label=f"profile manifest {path.name}",
                    path=path,
                )
            )

        return ProfilesResponse(
            source_dir=str(self.profiles_dir),
            active_profile=self.active_profile,
            total=len(items),
            items=items,
        )

    def list_compatibility(self) -> CompatibilityResponse:
        raw_items = self._load_yaml_list(
            self.compatibility_path,
            code="PROJECT_ULT_COMPATIBILITY_MATRIX_UNAVAILABLE",
            label="assembly compatibility matrix",
        )
        items = [
            self._validate_record(
                CompatibilityRecord,
                self._normalize_yaml_scalars(item),
                code="PROJECT_ULT_COMPATIBILITY_MATRIX_SCHEMA_INVALID",
                label="assembly compatibility matrix entry",
                path=self.compatibility_path,
                index=index,
            )
            for index, item in enumerate(raw_items)
        ]
        statuses = Counter(item.status for item in items)
        return CompatibilityResponse(
            source_path=str(self.compatibility_path),
            total=len(items),
            statuses=dict(sorted(statuses.items())),
            items=items,
        )

    def _try_modules(self) -> ModulesResponse:
        try:
            return self.list_modules()
        except ProjectUltApiError:
            return ModulesResponse(
                source_path=str(self.registry_path),
                total=0,
                statuses={},
                items=[],
            )

    def _try_profiles(self) -> ProfilesResponse:
        try:
            return self.list_profiles()
        except ProjectUltApiError:
            return ProfilesResponse(
                source_dir=str(self.profiles_dir),
                active_profile=self.active_profile,
                total=0,
                items=[],
            )

    def _try_compatibility(self) -> CompatibilityResponse:
        try:
            return self.list_compatibility()
        except ProjectUltApiError:
            return CompatibilityResponse(
                source_path=str(self.compatibility_path),
                total=0,
                statuses={},
                items=[],
            )

    def _default_compatibility_by_profile(
        self,
    ) -> dict[str, ProfileCompatibilityEvidence]:
        by_profile: dict[str, ProfileCompatibilityEvidence] = {}
        for item in self.list_compatibility().items:
            if item.extra_bundles:
                continue
            existing = by_profile.get(item.profile_id)
            if existing is not None and existing.status == "verified":
                continue
            by_profile[item.profile_id] = ProfileCompatibilityEvidence(
                status=item.status,
                verified_at=item.verified_at,
                matrix_version=item.matrix_version,
                extra_bundles=item.extra_bundles,
            )
        return by_profile

    def _artifact_statuses(self) -> list[SourceArtifact]:
        artifacts = [
            ("module_registry", self.registry_path),
            ("profiles_dir", self.profiles_dir),
            ("compatibility_matrix", self.compatibility_path),
        ]
        return [
            SourceArtifact(
                kind=kind,
                path=str(path),
                exists=path.exists(),
                message=None if path.exists() else "artifact not found",
            )
            for kind, path in artifacts
        ]

    def _load_yaml_list(
        self,
        path: Path,
        *,
        code: str,
        label: str,
    ) -> list[dict[str, Any]]:
        raw = self._load_yaml(path, code=code, label=label)
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ProjectUltApiError(
                code,
                f"Invalid {label}: YAML root must be a list",
                status_code=500,
                details={"path": str(path), "actual_type": type(raw).__name__},
            )
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ProjectUltApiError(
                    code,
                    f"Invalid {label}: list item must be a mapping",
                    status_code=500,
                    details={
                        "path": str(path),
                        "index": index,
                        "actual_type": type(item).__name__,
                    },
            )
        return raw

    def _validate_record(
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

    def _load_yaml_mapping(
        self,
        path: Path,
        *,
        code: str,
        label: str,
    ) -> dict[str, Any]:
        raw = self._load_yaml(path, code=code, label=label)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ProjectUltApiError(
                code,
                f"Invalid {label}: YAML root must be a mapping",
                status_code=500,
                details={"path": str(path), "actual_type": type(raw).__name__},
            )
        return raw

    def _load_yaml(self, path: Path, *, code: str, label: str) -> Any:
        self._ensure_path(path, code=code, label=label)
        try:
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ProjectUltApiError(
                code,
                f"Invalid YAML in {label}",
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

    def _ensure_path(self, path: Path, *, code: str, label: str) -> None:
        if path.exists():
            return
        raise ProjectUltApiError(
            code,
            f"Missing {label}",
            status_code=503,
            details={"path": str(path)},
        )

    def _normalize_yaml_scalars(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._normalize_yaml_scalars(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._normalize_yaml_scalars(item) for item in value]
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        return value
