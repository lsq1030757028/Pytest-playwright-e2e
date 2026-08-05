from datetime import timedelta

import pytest

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    Decision,
    DeterministicMemoryReference,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryRevision,
    PromotionRequest,
    ReadMode,
    StateEvent,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_owner,
    make_owner_acl,
    make_semantic_revision,
    make_source_hash,
    make_store,
)


def test_append_idempotency_cas_and_audit_chain() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()

    created = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="corr-create",
    )
    replayed = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="corr-replay",
    )
    changed_payload = revision.model_copy(
        update={"content": {"fact_candidate": "changed without new id"}}
    )

    assert created.decision is Decision.ACCEPTED
    assert replayed.decision is Decision.IDEMPOTENT_REPLAY
    assert store.verify_event_chain() is True
    with pytest.raises(MemoryContractError) as exc:
        store.append_revision(
            actor=owner,
            revision=changed_payload,
            expected_head_revision_id=None,
            correlation_id="corr-bad-idem",
        )
    assert exc.value.code is ErrorCode.DUPLICATE_IDEMPOTENCY_KEY


def test_stale_cas_returns_explicit_conflict_without_overwrite() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    revision_2 = MemoryRevision.create(
        memory_id=revision.memory_id,
        revision_nonce="revision-2",
        revision_number=2,
        parent_revision_refs=(revision.ref,),
        memory_kind=revision.memory_kind,
        namespace=revision.namespace,
        content={"fact_candidate": "The approved timeout is 45 seconds."},
        provenance=revision.provenance,
        retention_policy=revision.retention_policy,
        formation_event_ref="formation/event-2",
        created_by=owner.principal_id,
        idempotency_key="idem-revision-2",
        created_at=revision.created_at + timedelta(minutes=1),
    )
    accepted = store.compare_and_append_revision(
        actor=owner,
        revision=revision_2,
        expected_head_revision_id=revision.revision_id,
        correlation_id="append-2",
    )
    stale_revision = MemoryRevision.create(
        memory_id=revision.memory_id,
        revision_nonce="stale-revision",
        revision_number=2,
        parent_revision_refs=(revision.ref,),
        memory_kind=revision.memory_kind,
        namespace=revision.namespace,
        content={"fact_candidate": "stale branch"},
        provenance=revision.provenance,
        retention_policy=revision.retention_policy,
        formation_event_ref="formation/stale",
        created_by=owner.principal_id,
        idempotency_key="idem-stale",
        created_at=revision.created_at + timedelta(minutes=2),
    )
    conflict = store.compare_and_append_revision(
        actor=owner,
        revision=stale_revision,
        expected_head_revision_id=revision.revision_id,
        correlation_id="stale",
    )

    assert accepted.decision is Decision.ACCEPTED
    assert conflict.decision is Decision.CONFLICT
    assert conflict.error_code is ErrorCode.REVISION_CONFLICT
    assert conflict.conflict is not None
    assert conflict.conflict.current_head_revision_id == revision_2.revision_id
    assert store.get_head_revision(
        actor=owner, memory_id=revision.memory_id
    ).revision_id == revision_2.revision_id


def test_lifecycle_promotion_query_revoke_and_forget() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    verify_event = StateEvent.create(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        from_state=LifecycleState.CANDIDATE,
        to_state=LifecycleState.VERIFIED,
        reason_code="EVIDENCE_VERIFIED",
        actor_principal_ref=owner.principal_id,
        policy_decision_ref="policy/verify",
        occurred_at=FIXED_NOW,
        nonce="verify",
    )
    verified = store.append_state_event(
        actor=owner, event=verify_event, correlation_id="verify"
    )
    promotion = store.promote(
        actor=owner,
        request=PromotionRequest(
            memory_id=revision.memory_id,
            revision_id=revision.revision_id,
            declared_promotion_scope=revision.namespace,
            evidence_refs=("evidence/EV-1",),
            benchmark_or_evaluator_refs=("benchmark/M1.0",),
            promoter_principal_ref=owner.principal_id,
            policy_decision_ref="policy/promote",
            compatibility=None,
            effective_from=FIXED_NOW + timedelta(seconds=1),
            rollback_or_disable_ref="rollback/promotion-1",
        ),
        correlation_id="promote",
    )
    visible, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        now=FIXED_NOW + timedelta(seconds=2),
    )
    revoked = store.revoke_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="REQUIREMENT_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="revoke",
    )
    hidden, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        now=FIXED_NOW + timedelta(seconds=3),
    )
    tombstone = store.forget_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="PRIVACY_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="forget",
    )

    assert verified.effective_state is LifecycleState.VERIFIED
    assert promotion.effective_state is LifecycleState.PROMOTED
    assert [item.ref for item in visible] == [revision.ref]
    assert revoked.effective_state is LifecycleState.REVOKED
    assert hidden == ()
    assert tombstone.memory_id == revision.memory_id
    assert store.verify_cache_and_index_invalidation(memory_id=revision.memory_id)
    with pytest.raises(MemoryContractError) as exc:
        store.get_head_revision(actor=owner, memory_id=revision.memory_id)
    assert exc.value.code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE


def test_acl_deny_and_cross_project_query_fail_closed() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    deny = AclEntry(
        rule_id="deny-owner-read",
        effect=AclEffect.DENY,
        subject_type=AclSubjectType.PRINCIPAL,
        subject_id=owner.principal_id,
        operations=(AccessOperation.QUERY,),
        namespace=revision.namespace,
    )
    store = DeterministicMemoryReference(
        resolved_sources={"requirement/REQ-1@3": make_source_hash()},
        resolved_evidence=("evidence/EV-1",),
        initial_acl=(*make_owner_acl(make_namespace()), deny),
    )
    created = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    visible, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.ADVISORY,
    )

    assert created.decision is Decision.ACCEPTED
    assert visible == ()


def test_missing_provenance_is_rejected_without_success_audit() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = DeterministicMemoryReference(initial_acl=make_owner_acl())

    result = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="missing-provenance",
    )

    assert result.decision is Decision.REJECTED
    assert result.error_code is ErrorCode.PROVENANCE_MISSING
    assert store.list_audit_events() == ()
