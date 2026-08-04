from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CAPABILITY_NAME_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
ARTIFACT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"
ARTIFACT_TYPE_PATTERN = r"^[A-Z][A-Za-z0-9]*(?:\.[A-Z][A-Za-z0-9]*)*$"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ContextLevel(StrEnum):
    METADATA = "metadata"
    SUMMARY = "summary"
    FOCUSED = "focused"
    DEEP = "deep"


class CostClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IdempotencyMode(StrEnum):
    DETERMINISTIC = "deterministic"
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"


class RetryMode(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class CapabilityResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ArtifactValidity(StrEnum):
    VALID = "valid"
    CONDITIONALLY_VALID = "conditionally_valid"
    REQUIRES_REVIEW = "requires_review"
    REQUIRES_RERUN = "requires_rerun"
    SUPERSEDED = "superseded"
    INVALID = "invalid"
    HISTORICAL = "historical"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ArtifactTypeRef(FrozenModel):
    name: str = Field(pattern=ARTIFACT_TYPE_PATTERN)
    schema_version: int = Field(ge=1)

    @property
    def canonical_name(self) -> str:
        return f"{self.name}@{self.schema_version}"


class CapabilityRef(FrozenModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)

    @property
    def canonical_name(self) -> str:
        return f"{self.name}@{self.version}"


class RetryPolicy(FrozenModel):
    mode: RetryMode = RetryMode.NONE
    max_attempts: int = Field(default=1, ge=1, le=10)
    delay_seconds: float = Field(default=0, ge=0, le=300)
    max_delay_seconds: float = Field(default=0, ge=0, le=3600)

    @model_validator(mode="after")
    def validate_retry_shape(self) -> RetryPolicy:
        if self.mode == RetryMode.NONE and self.max_attempts != 1:
            raise ValueError("retry mode 'none' requires max_attempts=1")
        if self.mode != RetryMode.NONE and self.max_attempts < 2:
            raise ValueError("retry mode requires at least two attempts")
        if self.mode == RetryMode.EXPONENTIAL and self.max_delay_seconds < self.delay_seconds:
            raise ValueError("max_delay_seconds must be >= delay_seconds")
        return self


class ContextSelector(FrozenModel):
    namespace: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    keys: tuple[str, ...] = ()

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("context selector keys must be unique")
        for item in value:
            if not item or item == "*" or ".." in item:
                raise ValueError("context selector keys must be explicit and safe")
        return value


class ContextRequest(FrozenModel):
    level: ContextLevel = ContextLevel.METADATA
    selectors: tuple[ContextSelector, ...] = ()
    max_items: int = Field(default=100, ge=0, le=100_000)
    max_bytes: int = Field(default=1_000_000, ge=0, le=100_000_000)
    allow_secrets: bool = False

    @field_validator("selectors")
    @classmethod
    def validate_selectors(
        cls, value: tuple[ContextSelector, ...]
    ) -> tuple[ContextSelector, ...]:
        namespaces = [item.namespace for item in value]
        if len(namespaces) != len(set(namespaces)):
            raise ValueError("context selector namespaces must be unique")
        return value


class ExecutionBudget(FrozenModel):
    model_calls: int = Field(default=0, ge=0)
    token_limit: int = Field(default=0, ge=0)
    browser_sessions: int = Field(default=0, ge=0)
    api_calls: int = Field(default=0, ge=0)
    subprocesses: int = Field(default=0, ge=0)
    wall_time_seconds: float = Field(default=30, ge=0)
    artifact_bytes: int = Field(default=1_000_000, ge=0)
    retries: int = Field(default=0, ge=0)

    def as_usage_dict(self) -> dict[str, int | float]:
        return self.model_dump()


class PermissionScope(FrozenModel):
    read: frozenset[str] = frozenset()
    write: frozenset[str] = frozenset()
    execute: frozenset[str] = frozenset()
    network_domains: frozenset[str] = frozenset()
    allow_model: bool = False
    allow_browser: bool = False
    allow_subprocess: bool = False
    allow_secrets: bool = False

    @field_validator("read", "write", "execute", "network_domains")
    @classmethod
    def validate_scope_values(cls, value: frozenset[str]) -> frozenset[str]:
        for item in value:
            if not item or item == "*" or ".." in item:
                raise ValueError("permission scopes must be explicit and cannot contain '..'")
            if "*" in item and not item.endswith("/*"):
                raise ValueError("permission wildcard is only allowed as a trailing '/*'")
        return value


class CapabilityAccess(FrozenModel):
    allow_model: bool = False
    allow_network: bool = False
    allow_browser: bool = False
    allow_subprocess: bool = False


class CapabilityDescriptor(FrozenModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    input_types: tuple[ArtifactTypeRef, ...] = ()
    output_types: tuple[ArtifactTypeRef, ...] = ()
    side_effects: frozenset[str] = frozenset()
    cost_class: CostClass = CostClass.LOW
    default_context: ContextRequest = ContextRequest()
    required_permissions: PermissionScope = PermissionScope()
    access: CapabilityAccess = CapabilityAccess()
    idempotency: IdempotencyMode = IdempotencyMode.DETERMINISTIC
    retry_policy: RetryPolicy = RetryPolicy()
    timeout_seconds: float = Field(default=30, gt=0, le=86_400)
    tags: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def validate_descriptor(self) -> CapabilityDescriptor:
        input_names = [item.canonical_name for item in self.input_types]
        output_names = [item.canonical_name for item in self.output_types]
        if len(input_names) != len(set(input_names)):
            raise ValueError("input artifact types must be unique")
        if len(output_names) != len(set(output_names)):
            raise ValueError("output artifact types must be unique")
        if self.access.allow_model and not self.required_permissions.allow_model:
            raise ValueError("model access requires allow_model permission")
        if self.access.allow_browser and not self.required_permissions.allow_browser:
            raise ValueError("browser access requires allow_browser permission")
        if self.access.allow_subprocess and not self.required_permissions.allow_subprocess:
            raise ValueError("subprocess access requires allow_subprocess permission")
        if self.access.allow_network and not self.required_permissions.network_domains:
            raise ValueError("network access requires at least one allowed domain")
        return self

    @property
    def ref(self) -> CapabilityRef:
        return CapabilityRef(name=self.name, version=self.version)


class ArtifactRef(FrozenModel):
    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    artifact_type: str = Field(pattern=ARTIFACT_TYPE_PATTERN)
    schema_version: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    source_revisions: dict[str, str] = Field(default_factory=dict)
    created_by: CapabilityRef
    validity: ArtifactValidity = ArtifactValidity.VALID

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        if value.startswith("/") or value.endswith("/") or "//" in value or ".." in value:
            raise ValueError("artifact_id must be a safe relative identifier")
        return value

    @field_validator("source_revisions")
    @classmethod
    def validate_source_revisions(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or not revision for key, revision in value.items()):
            raise ValueError("source revision keys and values cannot be empty")
        return value


class CapabilityRequest(FrozenModel):
    request_id: str = Field(min_length=1, max_length=128)
    capability: CapabilityRef
    input_artifacts: tuple[ArtifactRef, ...] = ()
    context_request: ContextRequest = ContextRequest()
    budget: ExecutionBudget = ExecutionBudget()
    permissions: PermissionScope = PermissionScope()
    campaign_id: str | None = Field(default=None, max_length=128)
    correlation_id: str | None = Field(default=None, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_artifacts")
    @classmethod
    def validate_input_artifacts(
        cls, value: tuple[ArtifactRef, ...]
    ) -> tuple[ArtifactRef, ...]:
        artifact_ids = [item.artifact_id for item in value]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("input artifact ids must be unique")
        return value


class ExecutionMetrics(FrozenModel):
    duration_ms: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    browser_sessions: int = Field(default=0, ge=0)
    api_calls: int = Field(default=0, ge=0)
    subprocesses: int = Field(default=0, ge=0)
    artifact_bytes: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)


class DomainEvent(FrozenModel):
    event_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(pattern=EVENT_TYPE_PATTERN)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: CapabilityRef
    payload: dict[str, Any] = Field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO
    campaign_id: str | None = Field(default=None, max_length=128)
    correlation_id: str | None = Field(default=None, max_length=128)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class CapabilityResult(FrozenModel):
    request_id: str = Field(min_length=1, max_length=128)
    status: CapabilityResultStatus
    artifacts: tuple[ArtifactRef, ...] = ()
    events: tuple[DomainEvent, ...] = ()
    suggested_transition: str | None = Field(default=None, max_length=128)
    metrics: ExecutionMetrics = ExecutionMetrics()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    error: str | None = None

    @model_validator(mode="after")
    def validate_result_state(self) -> CapabilityResult:
        artifact_ids = [item.artifact_id for item in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("result artifact ids must be unique")
        if self.status == CapabilityResultStatus.SUCCESS:
            if self.blockers or self.error:
                raise ValueError("successful result cannot include blockers or an error")
        elif self.status == CapabilityResultStatus.FAILED:
            if not self.error:
                raise ValueError("failed result requires an error")
        elif self.status == CapabilityResultStatus.BLOCKED:
            if not self.blockers:
                raise ValueError("blocked result requires at least one blocker")
        return self


@runtime_checkable
class CapabilityExecutionContext(Protocol):
    def read_artifact(self, ref: ArtifactRef) -> dict[str, Any]: ...

    def write_artifact(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        schema_version: int,
        content: dict[str, Any],
        created_by: CapabilityRef,
        source_revisions: dict[str, str] | None = None,
    ) -> ArtifactRef: ...

    def emit(self, event: DomainEvent) -> None: ...


@runtime_checkable
class Capability(Protocol):
    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    def execute(
        self,
        request: CapabilityRequest,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult: ...
