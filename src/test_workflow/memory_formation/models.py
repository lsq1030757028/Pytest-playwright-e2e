from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..harness.contracts import ArtifactRef, ArtifactValidity
from ..memory_contracts import (
    LifecycleState,
    MemoryKind,
    MemoryNamespace,
    PrincipalContext,
    RetentionPolicy,
    canonical_sha256,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceClass(StrEnum):
    RUN_EVENT = "RUN_EVENT"
    TOOL_RESULT = "TOOL_RESULT"
    ARTIFACT = "ARTIFACT"
    REQUIREMENT_REVISION = "REQUIREMENT_REVISION"
    CODE_REVISION = "CODE_REVISION"
    ENVIRONMENT_REVISION = "ENVIRONMENT_REVISION"
    MEMORY_REVISION = "MEMORY_REVISION"
    HUMAN_ASSERTION = "HUMAN_ASSERTION"


class FormationMode(StrEnum):
    HOT_PATH = "HOT_PATH"
    BACKGROUND_CONSOLIDATION = "BACKGROUND_CONSOLIDATION"


class FormationStatus(StrEnum):
    CREATED_CANDIDATE = "CREATED_CANDIDATE"
    APPENDED_CANDIDATE_REVISION = "APPENDED_CANDIDATE_REVISION"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    CONFLICT_REQUIRES_REVIEW = "CONFLICT_REQUIRES_REVIEW"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    DEGRADED = "DEGRADED"


class SourceDescriptor(FrozenModel):
    source_class: SourceClass
    artifact_ref: ArtifactRef
    namespace: MemoryNamespace
    evaluator_only: bool = False
    holdout: bool = False
    sensitive: bool = False
    historical_only: bool = False

    @property
    def source_ref(self) -> str:
        return f"artifact/{self.artifact_ref.artifact_id}@{self.artifact_ref.content_hash}"

    @property
    def source_hash(self) -> str:
        prefix = "sha256:"
        if not self.artifact_ref.content_hash.startswith(prefix):
            raise ValueError("artifact content hash must be sha256-prefixed")
        return self.artifact_ref.content_hash.removeprefix(prefix)

    @model_validator(mode="after")
    def validate_artifact(self) -> SourceDescriptor:
        if self.artifact_ref.validity not in {
            ArtifactValidity.VALID,
            ArtifactValidity.HISTORICAL,
        }:
            raise ValueError("formation source must be valid or explicitly historical")
        if self.artifact_ref.validity is ArtifactValidity.HISTORICAL and not self.historical_only:
            raise ValueError("historical artifact must be labeled historical_only")
        return self


class EvidenceDescriptor(FrozenModel):
    artifact_ref: ArtifactRef
    namespace: MemoryNamespace
    evaluator_only: bool = False
    holdout: bool = False
    sensitive: bool = False

    @property
    def evidence_ref(self) -> str:
        return f"evidence/{self.artifact_ref.artifact_id}@{self.artifact_ref.content_hash}"


class FormationRequest(FrozenModel):
    request_id: str = Field(min_length=1, max_length=255)
    actor: PrincipalContext
    mode: FormationMode = FormationMode.HOT_PATH
    target_namespace: MemoryNamespace
    memory_kind: MemoryKind
    sources: tuple[SourceDescriptor, ...] = Field(min_length=1, max_length=16)
    evidence: tuple[EvidenceDescriptor, ...] = Field(min_length=1, max_length=16)
    authority_refs: tuple[str, ...] = Field(min_length=1)
    formation_rule_ref: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$")
    validator_profile_ref: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$")
    retention_policy: RetentionPolicy
    candidate_content: dict[str, Any]
    supporting_source_refs: tuple[str, ...] = ()
    requirement_revision_refs: tuple[str, ...] = ()
    code_revision_refs: tuple[str, ...] = ()
    environment_revision_refs: tuple[str, ...] = ()
    semantic_subject_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_head_revision_id: str | None = None
    historical_only: bool = False
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$")
    now: datetime

    @model_validator(mode="after")
    def validate_request(self) -> FormationRequest:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if self.mode is not FormationMode.HOT_PATH:
            raise ValueError("M1C-I1 supports HOT_PATH formation only")
        source_refs = tuple(source.source_ref for source in self.sources)
        if len(source_refs) != len(set(source_refs)):
            raise ValueError("duplicate source refs are not allowed")
        evidence_refs = tuple(item.evidence_ref for item in self.evidence)
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("duplicate evidence refs are not allowed")
        if self.memory_kind is MemoryKind.SEMANTIC and not self.supporting_source_refs:
            raise ValueError("semantic formation requires explicit supporting_source_refs")
        if not set(self.supporting_source_refs) <= set(source_refs):
            raise ValueError("supporting_source_refs must resolve to declared sources")
        if self.memory_kind is MemoryKind.WORKING and self.retention_policy.ttl_seconds is None:
            raise ValueError("working formation requires TTL")
        if self.memory_kind in {MemoryKind.PROCEDURAL, MemoryKind.SKILL}:
            raise ValueError("M1C-I1 does not admit procedural or skill runtime formation")
        return self

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


class FormationBudgetConsumption(FrozenModel):
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    elapsed_ms_before_store: int = Field(ge=0)


class FormationEvent(FrozenModel):
    event_id: str = Field(pattern=r"^formation_[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_principal_ref: str
    target_namespace: MemoryNamespace
    memory_kind: MemoryKind
    proposed_memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    formation_rule_ref: str
    occurred_at: datetime
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> FormationEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("formation event time must be timezone-aware")
        if self.event_hash != canonical_sha256(self.hash_payload()):
            raise ValueError("formation event hash mismatch")
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"event_hash"})

    @classmethod
    def create(
        cls,
        *,
        request: FormationRequest,
        proposed_memory_id: str,
        proposal_digest: str,
    ) -> FormationEvent:
        event_seed = {
            "request_digest": request.request_digest,
            "proposed_memory_id": proposed_memory_id,
            "proposal_digest": proposal_digest,
            "formation_rule_ref": request.formation_rule_ref,
        }
        event_id = f"formation_{canonical_sha256(event_seed)}"
        payload = {
            "event_id": event_id,
            "request_digest": request.request_digest,
            "actor_principal_ref": request.actor.principal_id,
            "target_namespace": request.target_namespace,
            "memory_kind": request.memory_kind,
            "proposed_memory_id": proposed_memory_id,
            "proposal_digest": proposal_digest,
            "formation_rule_ref": request.formation_rule_ref,
            "occurred_at": request.now,
        }
        return cls(**payload, event_hash=canonical_sha256(payload))


class FormationReplayEvidence(FrozenModel):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    formation_event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validator_profile_ref: str
    status: FormationStatus
    candidate_revision_ref: str | None = None
    candidate_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    store_audit_ref: str | None = None
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> FormationReplayEvidence:
        if self.manifest_digest != canonical_sha256(self.manifest_payload()):
            raise ValueError("formation replay manifest mismatch")
        return self

    def manifest_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"manifest_digest"})


class FormationResult(FrozenModel):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    formation_event_ref: str
    status: FormationStatus
    candidate_revision_ref: str | None = None
    candidate_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    effective_lifecycle: LifecycleState | None = None
    source_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate_ref: str | None = None
    conflict_refs: tuple[str, ...] = ()
    rejected_reasons: tuple[str, ...] = ()
    budget: FormationBudgetConsumption
    validator_profile_ref: str
    store_audit_ref: str | None = None
    replay_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
