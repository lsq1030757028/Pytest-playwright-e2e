from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import canonical_sha256

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
OPAQUE_ID_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FrozenDict(dict[str, Any]):
    """Recursively immutable JSON object used by governed revisions."""

    @staticmethod
    def _reject_mutation(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError("governed JSON values are immutable")

    __setitem__ = _reject_mutation
    __delitem__ = _reject_mutation
    clear = _reject_mutation
    pop = _reject_mutation
    popitem = _reject_mutation
    setdefault = _reject_mutation
    update = _reject_mutation


class MemoryKind(StrEnum):
    WORKING = "WORKING"
    SEMANTIC = "SEMANTIC"
    EPISODIC = "EPISODIC"
    PROCEDURAL = "PROCEDURAL"
    SKILL = "SKILL"


class LifecycleState(StrEnum):
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    PROMOTED = "PROMOTED"
    CONFLICTING = "CONFLICTING"
    QUARANTINED = "QUARANTINED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    FORGOTTEN = "FORGOTTEN"


class NamespaceScopeKind(StrEnum):
    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
    CAMPAIGN = "CAMPAIGN"
    AGENT = "AGENT"
    SHARED = "SHARED"


class PrincipalType(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SERVICE = "SERVICE"
    GROUP = "GROUP"
    SYSTEM_POLICY = "SYSTEM_POLICY"


class CreatorType(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SERVICE = "SERVICE"
    IMPORT = "IMPORT"
    DERIVATION = "DERIVATION"


class TransformationKind(StrEnum):
    RAW_OBSERVATION = "RAW_OBSERVATION"
    EXTRACTION = "EXTRACTION"
    SUMMARY = "SUMMARY"
    CONSOLIDATION = "CONSOLIDATION"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    PROCEDURE_COMPILATION = "PROCEDURE_COMPILATION"
    SKILL_REGISTRATION = "SKILL_REGISTRATION"


class AccessOperation(StrEnum):
    READ_METADATA = "READ_METADATA"
    READ_CONTENT = "READ_CONTENT"
    QUERY = "QUERY"
    APPEND_REVISION = "APPEND_REVISION"
    APPEND_STATE_EVENT = "APPEND_STATE_EVENT"
    VERIFY = "VERIFY"
    PROMOTE = "PROMOTE"
    SUPERSEDE = "SUPERSEDE"
    REVOKE = "REVOKE"
    FORGET = "FORGET"
    MANAGE_ACL = "MANAGE_ACL"
    AUDIT = "AUDIT"


class AclEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class AclSubjectType(StrEnum):
    PRINCIPAL = "PRINCIPAL"
    GROUP = "GROUP"
    ROLE = "ROLE"


class ReadMode(StrEnum):
    ADVISORY = "ADVISORY"
    EVIDENCE_BEARING = "EVIDENCE_BEARING"
    PRODUCTION_RETRIEVAL = "PRODUCTION_RETRIEVAL"


class ErrorCode(StrEnum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    NAMESPACE_DENIED = "NAMESPACE_DENIED"
    ACL_DENIED = "ACL_DENIED"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    DUPLICATE_IDEMPOTENCY_KEY = "DUPLICATE_IDEMPOTENCY_KEY"
    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION"
    PROVENANCE_MISSING = "PROVENANCE_MISSING"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    MEMORY_NOT_EFFECTIVE = "MEMORY_NOT_EFFECTIVE"
    PROMOTION_DENIED = "PROMOTION_DENIED"
    COMPATIBILITY_FAILED = "COMPATIBILITY_FAILED"
    FORGOTTEN_CONTENT_UNAVAILABLE = "FORGOTTEN_CONTENT_UNAVAILABLE"
    MEMORY_NOT_FOUND = "MEMORY_NOT_FOUND"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONFLICT = "CONFLICT"
    FILTERED = "FILTERED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"


class MemoryNamespace(FrozenModel):
    organization_id: str = Field(pattern=OPAQUE_ID_PATTERN)
    project_id: str | None = Field(default=None, pattern=OPAQUE_ID_PATTERN)
    scope_kind: NamespaceScopeKind
    scope_id: str = Field(pattern=OPAQUE_ID_PATTERN)

    @model_validator(mode="after")
    def validate_scope(self) -> MemoryNamespace:
        if self.scope_kind is NamespaceScopeKind.ORGANIZATION:
            if self.scope_id != self.organization_id:
                raise ValueError("organization scope_id must equal organization_id")
            if self.project_id is not None:
                raise ValueError("organization namespace must not declare project_id")
        else:
            if self.project_id is None:
                raise ValueError("project_id is required outside organization scope")
            if self.scope_kind is NamespaceScopeKind.PROJECT and self.scope_id != self.project_id:
                raise ValueError("project scope_id must equal project_id")
        return self

    @property
    def canonical(self) -> str:
        project = self.project_id or "-"
        return (
            f"org/{self.organization_id}/project/{project}/"
            f"scope/{self.scope_kind.value}/{self.scope_id}"
        )

    @property
    def namespace_hash(self) -> str:
        return canonical_sha256(self.canonical)


class PrincipalContext(FrozenModel):
    principal_id: str = Field(pattern=OPAQUE_ID_PATTERN)
    principal_type: PrincipalType
    authenticated: bool = True
    organization_id: str = Field(pattern=OPAQUE_ID_PATTERN)
    project_id: str | None = Field(default=None, pattern=OPAQUE_ID_PATTERN)
    campaign_id: str | None = Field(default=None, pattern=OPAQUE_ID_PATTERN)
    agent_id: str | None = Field(default=None, pattern=OPAQUE_ID_PATTERN)
    group_ids: tuple[str, ...] = ()
    role_ids: tuple[str, ...] = ()
    shared_scope_ids: tuple[str, ...] = ()
    delegator_ref: str | None = None
    delegation_scope: tuple[str, ...] = ()
    delegation_expires_at: datetime | None = None
    audit_event_ref: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> PrincipalContext:
        if not self.authenticated:
            raise ValueError("principal must be authenticated")
        delegated = self.delegator_ref is not None
        required = (
            bool(self.delegation_scope),
            self.delegation_expires_at is not None,
            self.audit_event_ref is not None,
        )
        if delegated != all(required):
            raise ValueError("delegated identity requires scope, expiry, and audit event")
        if self.delegation_expires_at is not None:
            _require_aware(self.delegation_expires_at, "delegation_expires_at")
        return self


class AclEntry(FrozenModel):
    rule_id: str = Field(pattern=OPAQUE_ID_PATTERN)
    effect: AclEffect
    subject_type: AclSubjectType
    subject_id: str = Field(pattern=OPAQUE_ID_PATTERN)
    operations: tuple[AccessOperation, ...] = Field(min_length=1)
    namespace: MemoryNamespace


class Provenance(FrozenModel):
    source_refs: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    source_content_hashes: dict[str, str] = Field(min_length=1)
    created_by_principal: str = Field(pattern=OPAQUE_ID_PATTERN)
    creator_type: CreatorType
    capability_or_formation_rule_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    requirement_revision_refs: tuple[str, ...] = ()
    code_revision_refs: tuple[str, ...] = ()
    environment_revision_refs: tuple[str, ...] = ()
    model_or_provider_profile_refs: tuple[str, ...] = ()
    parent_memory_refs: tuple[str, ...] = ()
    transformation_kind: TransformationKind

    @model_validator(mode="after")
    def validate_sources(self) -> Provenance:
        if set(self.source_content_hashes) != set(self.source_refs):
            raise ValueError("source_content_hashes must exactly cover source_refs")
        for digest in self.source_content_hashes.values():
            if re.fullmatch(SHA256_PATTERN, digest) is None:
                raise ValueError("source content hashes must be lowercase sha256")
        object.__setattr__(
            self,
            "source_content_hashes",
            _deep_freeze(self.source_content_hashes),
        )
        return self


class RetentionPolicy(FrozenModel):
    policy_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    ttl_seconds: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
    review_after: datetime | None = None
    campaign_close_at: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self) -> RetentionPolicy:
        for name in ("expires_at", "review_after", "campaign_close_at"):
            value = getattr(self, name)
            if value is not None:
                _require_aware(value, name)
        return self

    def effective_expiry(self, created_at: datetime) -> datetime | None:
        candidates: list[datetime] = []
        if self.ttl_seconds is not None:
            candidates.append(created_at + timedelta(seconds=self.ttl_seconds))
        if self.expires_at is not None:
            candidates.append(self.expires_at)
        if self.campaign_close_at is not None:
            candidates.append(self.campaign_close_at)
        return min(candidates) if candidates else None


class CompatibilityDescriptor(FrozenModel):
    project_architecture_families: tuple[str, ...] = Field(min_length=1)
    code_version_range: str = Field(min_length=1)
    schema_version_range: str = Field(min_length=1)
    capability_version_range: str = Field(min_length=1)
    model_profile_constraints: tuple[str, ...] = ()
    environment_constraints: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    incompatible_conditions: tuple[str, ...] = ()
    executable_ref: str | None = None

    @model_validator(mode="after")
    def validate_executable_ref(self) -> CompatibilityDescriptor:
        if self.executable_ref is not None:
            is_versioned = (
                self.executable_ref.startswith("capability://")
                and "@" in self.executable_ref
            )
            if not is_versioned:
                raise ValueError("executable_ref must resolve to a versioned capability")
        return self


class CompatibilityContext(FrozenModel):
    project_architecture_family: str
    code_version: str
    schema_version: str
    capability_version: str
    model_profile: str
    environment: str
    permissions: tuple[str, ...] = ()
    active_conditions: tuple[str, ...] = ()


class MemoryRevision(FrozenModel):
    memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^rev_[0-9a-f]{64}$")
    revision_number: int = Field(ge=1)
    parent_revision_refs: tuple[str, ...] = ()
    schema_version: str = Field(pattern=SEMVER_PATTERN)
    memory_kind: MemoryKind
    namespace: MemoryNamespace
    content: dict[str, Any]
    provenance: Provenance
    compatibility: CompatibilityDescriptor | None = None
    retention_policy: RetentionPolicy
    formation_event_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    created_at: datetime
    created_by: str = Field(pattern=OPAQUE_ID_PATTERN)
    idempotency_key: str = Field(pattern=OPAQUE_ID_PATTERN)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    EXECUTABLE_KEYS: ClassVar[frozenset[str]] = frozenset(
        {"shell", "script", "code", "command", "executable_payload", "raw_executable"}
    )

    @model_validator(mode="after")
    def validate_contract(self) -> MemoryRevision:
        _require_aware(self.created_at, "created_at")
        if self.revision_number == 1 and self.parent_revision_refs:
            raise ValueError("first revision must not have parents")
        if self.revision_number > 1 and not self.parent_revision_refs:
            raise ValueError("later revisions require a parent revision")
        if len(self.parent_revision_refs) > 1 and (
            self.provenance.transformation_kind is not TransformationKind.CONFLICT_RESOLUTION
        ):
            raise ValueError("multiple parents require explicit conflict resolution provenance")
        if self.memory_kind is MemoryKind.WORKING:
            if self.retention_policy.ttl_seconds is None:
                raise ValueError("working memory requires ttl_seconds")
        if self.memory_kind in {MemoryKind.PROCEDURAL, MemoryKind.SKILL}:
            if self.compatibility is None:
                raise ValueError("procedural and skill memory require compatibility metadata")
            forbidden = _find_forbidden_keys(self.content, self.EXECUTABLE_KEYS)
            if forbidden:
                raise ValueError(
                    "unrestricted executable payload is forbidden: " + ", ".join(sorted(forbidden))
                )
        elif self.compatibility is not None:
            raise ValueError("compatibility metadata is reserved for procedural and skill memory")
        if self.content_hash != canonical_sha256(self.hash_payload()):
            raise ValueError("content_hash does not match canonical governed payload")
        object.__setattr__(self, "content", _deep_freeze(self.content))
        return self

    def hash_payload(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "revision_id": self.revision_id,
            "schema_version": self.schema_version,
            "memory_kind": self.memory_kind,
            "namespace": self.namespace,
            "content": self.content,
            "provenance": self.provenance,
            "compatibility": self.compatibility,
            "retention_policy": self.retention_policy,
        }

    @classmethod
    def create(
        cls,
        *,
        memory_kind: MemoryKind,
        namespace: MemoryNamespace,
        content: dict[str, Any],
        provenance: Provenance,
        retention_policy: RetentionPolicy,
        formation_event_ref: str,
        created_by: str,
        idempotency_key: str,
        compatibility: CompatibilityDescriptor | None = None,
        memory_id: str | None = None,
        revision_number: int = 1,
        parent_revision_refs: tuple[str, ...] = (),
        schema_version: str = "1.0.0",
        created_at: datetime | None = None,
        revision_nonce: str | None = None,
    ) -> MemoryRevision:
        resolved_memory_id = memory_id or f"mem_{uuid4().hex}"
        nonce = revision_nonce or uuid4().hex
        revision_seed = {
            "memory_id": resolved_memory_id,
            "revision_number": revision_number,
            "parents": parent_revision_refs,
            "nonce": nonce,
        }
        revision_id = f"rev_{canonical_sha256(revision_seed)}"
        resolved_created_at = created_at or datetime.now(UTC)
        payload = {
            "memory_id": resolved_memory_id,
            "revision_id": revision_id,
            "schema_version": schema_version,
            "memory_kind": memory_kind,
            "namespace": namespace,
            "content": content,
            "provenance": provenance,
            "compatibility": compatibility,
            "retention_policy": retention_policy,
        }
        return cls(
            memory_id=resolved_memory_id,
            revision_id=revision_id,
            revision_number=revision_number,
            parent_revision_refs=parent_revision_refs,
            schema_version=schema_version,
            memory_kind=memory_kind,
            namespace=namespace,
            content=content,
            provenance=provenance,
            compatibility=compatibility,
            retention_policy=retention_policy,
            formation_event_ref=formation_event_ref,
            created_at=resolved_created_at,
            created_by=created_by,
            idempotency_key=idempotency_key,
            content_hash=canonical_sha256(payload),
        )

    @property
    def ref(self) -> str:
        return f"{self.memory_id}@{self.revision_id}"


class StateEvent(FrozenModel):
    state_event_id: str = Field(pattern=r"^state_[0-9a-f]{64}$")
    memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^rev_[0-9a-f]{64}$")
    from_state: LifecycleState
    to_state: LifecycleState
    reason_code: str = Field(pattern=OPAQUE_ID_PATTERN)
    actor_principal_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    policy_decision_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    occurred_at: datetime
    event_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_hash(self) -> StateEvent:
        _require_aware(self.occurred_at, "occurred_at")
        if self.event_hash != canonical_sha256(self.hash_payload()):
            raise ValueError("state event hash mismatch")
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"event_hash"})

    @classmethod
    def create(
        cls,
        *,
        memory_id: str,
        revision_id: str,
        from_state: LifecycleState,
        to_state: LifecycleState,
        reason_code: str,
        actor_principal_ref: str,
        policy_decision_ref: str,
        occurred_at: datetime | None = None,
        nonce: str | None = None,
    ) -> StateEvent:
        resolved_at = occurred_at or datetime.now(UTC)
        seed = {
            "memory_id": memory_id,
            "revision_id": revision_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason_code": reason_code,
            "actor": actor_principal_ref,
            "policy": policy_decision_ref,
            "occurred_at": resolved_at,
            "nonce": nonce or uuid4().hex,
        }
        state_event_id = f"state_{canonical_sha256(seed)}"
        payload = {
            "state_event_id": state_event_id,
            "memory_id": memory_id,
            "revision_id": revision_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason_code": reason_code,
            "actor_principal_ref": actor_principal_ref,
            "policy_decision_ref": policy_decision_ref,
            "occurred_at": resolved_at,
        }
        return cls(**payload, event_hash=canonical_sha256(payload))


class PromotionRequest(FrozenModel):
    memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^rev_[0-9a-f]{64}$")
    declared_promotion_scope: MemoryNamespace
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    benchmark_or_evaluator_refs: tuple[str, ...] = Field(min_length=1)
    promoter_principal_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    policy_decision_ref: str = Field(pattern=OPAQUE_ID_PATTERN)
    compatibility: CompatibilityDescriptor | None
    effective_from: datetime
    rollback_or_disable_ref: str = Field(pattern=OPAQUE_ID_PATTERN)

    @model_validator(mode="after")
    def validate_time(self) -> PromotionRequest:
        _require_aware(self.effective_from, "effective_from")
        return self


class ConflictArtifact(FrozenModel):
    conflict_id: str = Field(pattern=r"^conflict_[0-9a-f]{64}$")
    memory_id: str
    base_revision_id: str | None
    current_head_revision_id: str | None
    attempted_revision_id: str
    conflicting_fields: tuple[str, ...] = Field(min_length=1)
    detected_at: datetime
    actor_ref: str

    @model_validator(mode="after")
    def validate_time(self) -> ConflictArtifact:
        _require_aware(self.detected_at, "detected_at")
        return self


class ForgetTombstone(FrozenModel):
    memory_id: str
    namespace_hash: str = Field(pattern=SHA256_PATTERN)
    memory_kind: MemoryKind
    forgotten_at: datetime
    reason_code: str
    authority_event_ref: str
    prior_revision_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_time(self) -> ForgetTombstone:
        _require_aware(self.forgotten_at, "forgotten_at")
        return self


class PermissionDecision(FrozenModel):
    decision: Decision
    operation: AccessOperation
    namespace: str
    matched_rule_ids: tuple[str, ...] = ()
    error_code: ErrorCode | None = None
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class TransitionDecision(FrozenModel):
    decision: Decision
    from_state: LifecycleState
    to_state: LifecycleState
    error_code: ErrorCode | None = None
    reason: str


class EffectiveReadDecision(FrozenModel):
    decision: Decision
    state: LifecycleState
    read_mode: ReadMode
    error_code: ErrorCode | None = None
    reason: str


class PromotionDecision(FrozenModel):
    decision: Decision
    error_code: ErrorCode | None = None
    reason: str


class AppendRevisionResult(FrozenModel):
    decision: Decision
    effective_revision_ref: str | None = None
    effective_state: LifecycleState | None = None
    audit_event_ref: str | None = None
    revision: MemoryRevision | None = None
    conflict: ConflictArtifact | None = None
    error_code: ErrorCode | None = None


class MutationResult(FrozenModel):
    decision: Decision
    effective_revision_ref: str | None = None
    effective_state: LifecycleState | None = None
    audit_event_ref: str | None = None
    error_code: ErrorCode | None = None


class AuditEvent(FrozenModel):
    event_id: str = Field(pattern=r"^audit_[0-9a-f]{64}$")
    event_type: str = Field(pattern=OPAQUE_ID_PATTERN)
    memory_id: str
    revision_id: str
    namespace: MemoryNamespace
    actor_principal_ref: str
    occurred_at: datetime
    reason_code: str
    policy_decision_ref: str
    previous_event_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    event_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_hash(self) -> AuditEvent:
        _require_aware(self.occurred_at, "occurred_at")
        if self.event_hash != canonical_sha256(self.hash_payload()):
            raise ValueError("audit event hash mismatch")
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"event_hash"})


class MemoryContractError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return FrozenDict({key: _deep_freeze(nested) for key, nested in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(nested) for nested in value)
    return value


def _find_forbidden_keys(value: Any, forbidden: frozenset[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in forbidden:
                found.add(key)
            found.update(_find_forbidden_keys(nested, forbidden))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_find_forbidden_keys(nested, forbidden))
    return found
