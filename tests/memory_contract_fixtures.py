from datetime import UTC, datetime, timedelta

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    CreatorType,
    DeterministicMemoryReference,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    PrincipalContext,
    PrincipalType,
    Provenance,
    RetentionPolicy,
    TransformationKind,
    canonical_sha256,
)

FIXED_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def make_namespace() -> MemoryNamespace:
    return MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.PROJECT,
        scope_id="project-1",
    )


def make_owner() -> PrincipalContext:
    return PrincipalContext(
        principal_id="agent-owner",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-1",
        agent_id="agent-owner",
        role_ids=("OWNER", "VERIFIER", "PROMOTER", "PRIVACY_CONTROLLER"),
    )


def make_owner_acl(namespace: MemoryNamespace | None = None) -> tuple[AclEntry, ...]:
    resolved = namespace or make_namespace()
    return (
        AclEntry(
            rule_id="bootstrap-manage-acl",
            effect=AclEffect.ALLOW,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id="agent-owner",
            operations=(AccessOperation.MANAGE_ACL,),
            namespace=resolved,
        ),
    )


def make_source_hash() -> str:
    return canonical_sha256({"source": "approved requirement"})


def make_provenance() -> Provenance:
    source_hash = make_source_hash()
    return Provenance(
        source_refs=("requirement/REQ-1@3",),
        evidence_refs=("evidence/EV-1",),
        source_content_hashes={"requirement/REQ-1@3": source_hash},
        created_by_principal="agent-owner",
        creator_type=CreatorType.AGENT,
        capability_or_formation_rule_ref="formation/m1a-explicit",
        requirement_revision_refs=("requirement/REQ-1@3",),
        code_revision_refs=("code/abc123",),
        environment_revision_refs=("env/test@1",),
        model_or_provider_profile_refs=("model/deterministic@1",),
        transformation_kind=TransformationKind.EXTRACTION,
    )


def make_semantic_revision() -> MemoryRevision:
    return MemoryRevision.create(
        memory_id="mem_11111111111111111111111111111111",
        revision_nonce="semantic-1",
        memory_kind=MemoryKind.SEMANTIC,
        namespace=make_namespace(),
        content={"fact_candidate": "The current approved timeout is 30 seconds."},
        provenance=make_provenance(),
        retention_policy=RetentionPolicy(
            policy_ref="retention/semantic-v1",
            review_after=FIXED_NOW + timedelta(days=30),
        ),
        formation_event_ref="formation/event-1",
        created_by="agent-owner",
        idempotency_key="idem-semantic-1",
        created_at=FIXED_NOW,
    )


def make_store() -> DeterministicMemoryReference:
    namespace = make_namespace()
    return DeterministicMemoryReference(
        resolved_sources={"requirement/REQ-1@3": make_source_hash()},
        resolved_evidence=("evidence/EV-1",),
        resolved_benchmarks=("benchmark/M1.0",),
        initial_acl=make_owner_acl(namespace),
    )
