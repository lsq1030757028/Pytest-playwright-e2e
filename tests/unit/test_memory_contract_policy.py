from datetime import timedelta

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    CompatibilityContext,
    CompatibilityDescriptor,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    PrincipalContext,
    PrincipalType,
    PromotionRequest,
    ReadMode,
    RetentionPolicy,
    TransformationKind,
    evaluate_effective_read,
    evaluate_permission,
    validate_promotion,
    validate_transition,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_owner,
    make_provenance,
    make_semantic_revision,
)


def test_namespace_is_checked_before_acl_or_relevance() -> None:
    namespace = make_namespace()
    outsider = PrincipalContext(
        principal_id="agent-outsider",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-2",
        agent_id="agent-outsider",
        role_ids=("OWNER",),
    )
    allow = AclEntry(
        rule_id="allow-outsider",
        effect=AclEffect.ALLOW,
        subject_type=AclSubjectType.PRINCIPAL,
        subject_id="agent-outsider",
        operations=(AccessOperation.READ_CONTENT,),
        namespace=namespace,
    )

    decision = evaluate_permission(
        actor=outsider,
        namespace=namespace,
        operation=AccessOperation.READ_CONTENT,
        acl_entries=(allow,),
        relevance_score=1.0,
    )

    assert decision.decision is Decision.DENY
    assert decision.error_code is ErrorCode.NAMESPACE_DENIED


def test_explicit_deny_overrides_principal_allow_and_role_allow() -> None:
    namespace = make_namespace()
    owner = make_owner()
    entries = (
        AclEntry(
            rule_id="allow-owner",
            effect=AclEffect.ALLOW,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id=owner.principal_id,
            operations=(AccessOperation.READ_CONTENT,),
            namespace=namespace,
        ),
        AclEntry(
            rule_id="deny-owner",
            effect=AclEffect.DENY,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id=owner.principal_id,
            operations=(AccessOperation.READ_CONTENT,),
            namespace=namespace,
        ),
    )

    decision = evaluate_permission(
        actor=owner,
        namespace=namespace,
        operation=AccessOperation.READ_CONTENT,
        acl_entries=entries,
    )

    assert decision.decision is Decision.DENY
    assert decision.matched_rule_ids == ("deny-owner",)


def test_shared_scope_requires_explicit_membership_even_with_role() -> None:
    shared = MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.SHARED,
        scope_id="share-red",
    )
    actor = PrincipalContext(
        principal_id="agent-2",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-2",
        agent_id="agent-2",
        role_ids=("OWNER",),
    )

    denied = evaluate_permission(
        actor=actor,
        namespace=shared,
        operation=AccessOperation.QUERY,
    )
    allowed_actor = actor.model_copy(update={"shared_scope_ids": ("share-red",)})
    allowed = evaluate_permission(
        actor=allowed_actor,
        namespace=shared,
        operation=AccessOperation.QUERY,
    )

    assert denied.error_code is ErrorCode.NAMESPACE_DENIED
    assert allowed.decision is Decision.ALLOW


def test_lifecycle_rejects_direct_candidate_promotion_and_forgotten_revival() -> None:
    assert validate_transition(
        LifecycleState.CANDIDATE, LifecycleState.PROMOTED
    ).error_code is ErrorCode.ILLEGAL_TRANSITION
    assert validate_transition(
        LifecycleState.VERIFIED, LifecycleState.PROMOTED
    ).decision is Decision.ACCEPTED
    assert validate_transition(
        LifecycleState.FORGOTTEN, LifecycleState.CANDIDATE
    ).error_code is ErrorCode.ILLEGAL_TRANSITION


def test_promotion_is_only_retrieval_admission() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    permission = evaluate_permission(
        actor=owner,
        namespace=revision.namespace,
        operation=AccessOperation.PROMOTE,
    )
    request = PromotionRequest(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        declared_promotion_scope=revision.namespace,
        evidence_refs=("evidence/EV-1",),
        benchmark_or_evaluator_refs=("benchmark/M1.0",),
        promoter_principal_ref=owner.principal_id,
        policy_decision_ref="policy/promotion-allow",
        compatibility=None,
        effective_from=FIXED_NOW,
        rollback_or_disable_ref="rollback/promotion-1",
    )

    denied = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.CANDIDATE,
        request=request,
        permission=permission,
        resolved_evidence=frozenset({"evidence/EV-1"}),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )
    allowed = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.VERIFIED,
        request=request,
        permission=permission,
        resolved_evidence=frozenset({"evidence/EV-1"}),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )

    assert denied.error_code is ErrorCode.PROMOTION_DENIED
    assert allowed.decision is Decision.ACCEPTED
    assert "protected authority is unchanged" in allowed.reason


def test_expiration_and_compatibility_filter_before_effective_read() -> None:
    working = MemoryRevision.create(
        memory_kind=MemoryKind.WORKING,
        namespace=make_namespace(),
        content={"turn": "transient"},
        provenance=make_provenance(),
        retention_policy=RetentionPolicy(policy_ref="working", ttl_seconds=10),
        formation_event_ref="formation/working",
        created_by="agent-owner",
        idempotency_key="idem-working",
        created_at=FIXED_NOW,
    )
    expired = evaluate_effective_read(
        revision=working,
        state=LifecycleState.CANDIDATE,
        read_mode=ReadMode.ADVISORY,
        now=FIXED_NOW + timedelta(seconds=11),
    )

    compatibility = CompatibilityDescriptor(
        project_architecture_families=("python-web",),
        code_version_range="1.x",
        schema_version_range="1.x",
        capability_version_range="1.x",
        required_permissions=("browser.read",),
        executable_ref="capability://browser-check@1.0.0",
    )
    skill = MemoryRevision.create(
        memory_kind=MemoryKind.SKILL,
        namespace=make_namespace(),
        content={"capability_ref": "browser-check"},
        provenance=make_provenance().model_copy(
            update={"transformation_kind": TransformationKind.SKILL_REGISTRATION}
        ),
        compatibility=compatibility,
        retention_policy=RetentionPolicy(policy_ref="skill"),
        formation_event_ref="formation/skill",
        created_by="agent-owner",
        idempotency_key="idem-skill",
        created_at=FIXED_NOW,
    )
    incompatible = evaluate_effective_read(
        revision=skill,
        state=LifecycleState.PROMOTED,
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        compatibility_context=CompatibilityContext(
            project_architecture_family="python-web",
            code_version="1.0.0",
            schema_version="1.0.0",
            capability_version="1.0.0",
            model_profile="deterministic",
            environment="test",
            permissions=(),
        ),
        now=FIXED_NOW,
    )

    assert expired.state is LifecycleState.EXPIRED
    assert incompatible.error_code is ErrorCode.COMPATIBILITY_FAILED


def test_campaign_namespace_requires_exact_campaign_context() -> None:
    campaign = MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.CAMPAIGN,
        scope_id="campaign-red",
    )
    wrong_campaign = make_owner().model_copy(update={"campaign_id": "campaign-blue"})
    exact_campaign = make_owner().model_copy(update={"campaign_id": "campaign-red"})

    denied = evaluate_permission(
        actor=wrong_campaign, namespace=campaign, operation=AccessOperation.QUERY
    )
    allowed = evaluate_permission(
        actor=exact_campaign, namespace=campaign, operation=AccessOperation.QUERY
    )

    assert denied.error_code is ErrorCode.NAMESPACE_DENIED
    assert allowed.decision is Decision.ALLOW


def test_delegation_scope_and_expiry_fail_closed() -> None:
    namespace = make_namespace()
    active = make_owner().model_copy(
        update={
            "delegator_ref": "user/owner",
            "delegation_scope": (namespace.canonical,),
            "delegation_expires_at": FIXED_NOW + timedelta(minutes=5),
            "audit_event_ref": "audit/delegation-1",
        }
    )
    expired = active.model_copy(
        update={"delegation_expires_at": FIXED_NOW - timedelta(seconds=1)}
    )
    out_of_scope = active.model_copy(update={"delegation_scope": ("other/scope",)})

    assert evaluate_permission(
        actor=active,
        namespace=namespace,
        operation=AccessOperation.QUERY,
        now=FIXED_NOW,
    ).decision is Decision.ALLOW
    assert evaluate_permission(
        actor=expired,
        namespace=namespace,
        operation=AccessOperation.QUERY,
        now=FIXED_NOW,
    ).error_code is ErrorCode.NAMESPACE_DENIED
    assert evaluate_permission(
        actor=out_of_scope,
        namespace=namespace,
        operation=AccessOperation.QUERY,
        now=FIXED_NOW,
    ).error_code is ErrorCode.NAMESPACE_DENIED


def test_version_ranges_are_enforced_for_skill_memory() -> None:
    compatibility = CompatibilityDescriptor(
        project_architecture_families=("python-web",),
        code_version_range=">=1,<2",
        schema_version_range="1.x",
        capability_version_range="1.2.x",
        required_permissions=("browser.read",),
        executable_ref="capability://browser-check@1.2.0",
    )
    skill = MemoryRevision.create(
        memory_kind=MemoryKind.SKILL,
        namespace=make_namespace(),
        content={"capability_ref": "browser-check"},
        provenance=make_provenance().model_copy(
            update={"transformation_kind": TransformationKind.SKILL_REGISTRATION}
        ),
        compatibility=compatibility,
        retention_policy=RetentionPolicy(policy_ref="skill"),
        formation_event_ref="formation/skill-version",
        created_by="agent-owner",
        idempotency_key="idem-skill-version",
        created_at=FIXED_NOW,
    )
    context = CompatibilityContext(
        project_architecture_family="python-web",
        code_version="2.0.0",
        schema_version="1.0.0",
        capability_version="1.2.5",
        model_profile="deterministic",
        environment="test",
        permissions=("browser.read",),
    )

    decision = evaluate_effective_read(
        revision=skill,
        state=LifecycleState.PROMOTED,
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        compatibility_context=context,
        now=FIXED_NOW,
    )

    assert decision.error_code is ErrorCode.COMPATIBILITY_FAILED


def test_promotion_rejects_actor_or_unresolved_evidence_mismatch() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    permission = evaluate_permission(
        actor=owner, namespace=revision.namespace, operation=AccessOperation.PROMOTE
    )
    request = PromotionRequest(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        declared_promotion_scope=revision.namespace,
        evidence_refs=("evidence/EV-1",),
        benchmark_or_evaluator_refs=("benchmark/M1.0",),
        promoter_principal_ref="agent-other",
        policy_decision_ref="policy/promotion-allow",
        compatibility=None,
        effective_from=FIXED_NOW,
        rollback_or_disable_ref="rollback/promotion-1",
    )

    actor_mismatch = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.VERIFIED,
        request=request,
        permission=permission,
        resolved_evidence=frozenset({"evidence/EV-1"}),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )
    unresolved = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.VERIFIED,
        request=request.model_copy(update={"promoter_principal_ref": owner.principal_id}),
        permission=permission,
        resolved_evidence=frozenset(),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )

    assert actor_mismatch.error_code is ErrorCode.PROMOTION_DENIED
    assert unresolved.error_code is ErrorCode.PROMOTION_DENIED
