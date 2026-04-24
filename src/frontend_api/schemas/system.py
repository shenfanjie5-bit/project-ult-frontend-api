"""System and assembly-facing API response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from frontend_api.schemas.common import JsonDict, ServiceIdentity, SourceArtifact


HealthStatus = Literal["healthy", "degraded", "unhealthy"]


class PublicEntrypoint(BaseModel):
    name: str
    kind: str
    reference: str


class ModuleRecord(BaseModel):
    module_id: str
    module_version: str
    contract_version: str
    owner: str
    upstream_modules: list[str] = Field(default_factory=list)
    downstream_modules: list[str] = Field(default_factory=list)
    public_entrypoints: list[PublicEntrypoint] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    supported_profiles: list[str] = Field(default_factory=list)
    integration_status: str
    last_smoke_result: str | None = None
    notes: str = ""


class ModulesResponse(BaseModel):
    source_path: str
    total: int
    statuses: dict[str, int] = Field(default_factory=dict)
    items: list[ModuleRecord]


class StorageBackend(BaseModel):
    kind: str
    connection: dict[str, str] = Field(default_factory=dict)


class ResourceExpectation(BaseModel):
    cpu_cores: float
    memory_gb: float
    disk_gb: float


class ProfileCompatibilityEvidence(BaseModel):
    status: str | None = None
    verified_at: str | None = None
    matrix_version: str | None = None
    extra_bundles: list[str] = Field(default_factory=list)


class ProfileRecord(BaseModel):
    profile_id: str
    mode: str
    enabled_modules: list[str] = Field(default_factory=list)
    enabled_service_bundles: list[str] = Field(default_factory=list)
    required_env_keys: list[str] = Field(default_factory=list)
    optional_env_keys: list[str] = Field(default_factory=list)
    storage_backends: dict[str, StorageBackend] = Field(default_factory=dict)
    resource_expectation: ResourceExpectation
    max_long_running_daemons: int
    notes: str = ""
    compatibility: ProfileCompatibilityEvidence


class ProfilesResponse(BaseModel):
    source_dir: str
    active_profile: str
    total: int
    items: list[ProfileRecord]


class CompatibilityModuleRef(BaseModel):
    module_id: str
    module_version: str


class CompatibilityRecord(BaseModel):
    matrix_version: str
    profile_id: str
    extra_bundles: list[str] = Field(default_factory=list)
    module_set: list[CompatibilityModuleRef] = Field(default_factory=list)
    contract_version: str
    required_tests: list[str] = Field(default_factory=list)
    status: str
    verified_at: str | None = None


class CompatibilityResponse(BaseModel):
    source_path: str
    total: int
    statuses: dict[str, int] = Field(default_factory=dict)
    items: list[CompatibilityRecord]


class HealthSummary(BaseModel):
    total: int = 0
    details: JsonDict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: HealthStatus
    service: ServiceIdentity
    project_root: str
    assembly_root: str
    artifacts: list[SourceArtifact]
    modules: HealthSummary
    profiles: HealthSummary
    compatibility: HealthSummary
    message: str


class RawYamlList(BaseModel):
    items: list[dict[str, Any]]
