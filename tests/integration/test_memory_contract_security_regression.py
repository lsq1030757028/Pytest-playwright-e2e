from datetime import timedelta

import pytest

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryRevision,
    PrincipalContext,
    PrincipalType,
    PromotionRequest,
    ReadMode,
    StateEvent,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_owner,
    make_semantic_revision,
    make_store,
)


def _next_revision(parent: MemoryRevision, *, key: str = "idem-semantic-2") -> MemoryRevision:
    return MemoryRevision.create(
        memory_id=parent.memory_id,
        revision_nonce="semantic-2",
        revision_number=2,
        parent_revision_refs=(parent.ref,),
        memory_kind=parent.memory_kind,
        namespace=parent.namespace,
        content={"fact_candidate": "The current approved timeout is 45 seconds."},
        provenance=parent.provenance,
        retention_policy=parent.retention_policy,
        formation_event_ref="formation/event-2",
        created_by="agent-owner",
        idempotency_key=key,
        created_at=FIXED_NOW + timedelta(minutes=1),
    )


def _promote_first_revision(store, owner, revision) -> None:
    verified = StateEvent.create(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        from_state=LifecycleState.CANDIDATE,
        to_state=LifecycleState.VERIFIED,
        reason_code="EVIDENCE_VERIFIED",
        actor_principal_ref=owner.principal_id,
        policy_decision_ref="policy/verify",
        occurred_at=FIXED_NOW,
        nonce="security-verify",
    )
    assert store.append_state_event(
        actor=owner,
        event=verified,
        correlation_id="security-verify",
    ).decision is Decision.ACCEPTED
    promoted = store.promote(
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
            rollback_or_disable_ref="rollback/security-promotion",
        ),
        correlation_id="security-promote",
    )
    assert promoted.effective_state is LifecycleState.PROMOTED


def _forget(store, owner, revision) -> None:
    store.revoke_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="REVOKE",
        policy_decision_ref="policy/revoke",
        correlation_id="revoke",
    )
    store.forget_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="forget",
    )


def test_new_revision_does_not_inherit_promoted_state() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    assert store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create-first",
    ).decision is Decision.ACCEPTED
    _promote_first_revision(store, owner, revision)

    second = _next_revision(revision)
    appended = store.append_revision(
        actor=owner,
        revision=second,
        expected_head_revision_id=revision.revision_id,
        correlation_id="append-second",
    )
    production, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        now=FIXED_NOW + timedelta(minutes=2),
    )
    advisory, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.ADVISORY,
        now=FIXED_NOW + timedelta(minutes=2),
    )

    assert appended.decision is Decision.ACCEPTED
    assert appended.effective_state is LifecycleState.CANDIDATE
    assert store.get_effective_state(memory_id=revision.memory_id) is LifecycleState.CANDIDATE
    assert production == ()
    assert advisory == (second,)


def test_idempotency_replay_is_bound_to_current_permission_actor_and_cas_request() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    created = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    replay = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="replay",
    )
    unprivileged = PrincipalContext(
        principal_id="agent-unprivileged",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-1",
        agent_id="agent-unprivileged",
    )
    denied = store.append_revision(
        actor=unprivileged,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="unauthorized-replay",
    )

    assert created.decision is Decision.ACCEPTED
    assert replay == created
    assert denied.decision is Decision.REJECTED
    assert denied.error_code is ErrorCode.ACL_DENIED
    with pytest.raises(MemoryContractError) as exc:
        store.append_revision(
            actor=owner,
            revision=revision,
            expected_head_revision_id="rev_" + "0" * 64,
            correlation_id="changed-cas-request",
        )
    assert exc.value.code is ErrorCode.DUPLICATE_IDEMPOTENCY_KEY


def test_idempotency_replay_rechecks_permission_for_same_actor() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    created = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create-before-deny",
    )
    deny_owner_append = AclEntry(
        rule_id="deny-owner-append",
        effect=AclEffect.DENY,
        subject_type=AclSubjectType.PRINCIPAL,
        subject_id=owner.principal_id,
        operations=(AccessOperation.APPEND_REVISION,),
        namespace=revision.namespace,
    )
    acl_result = store.append_acl_event(
        actor=owner,
        entry=deny_owner_append,
        correlation_id="deny-owner-append",
    )
    replay = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="replay-after-deny",
    )

    assert created.decision is Decision.ACCEPTED
    assert acl_result.decision is Decision.ACCEPTED
    assert replay.decision is Decision.REJECTED
    assert replay.error_code is ErrorCode.ACL_DENIED


def test_forgotten_memory_id_cannot_accept_or_replay_content_revision() -> None:
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store()
    created = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    _forget(store, owner, revision)

    replay = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="replay-after-forget",
    )
    later = store.append_revision(
        actor=owner,
        revision=_next_revision(revision, key="idem-after-forget"),
        expected_head_revision_id=revision.revision_id,
        correlation_id="append-after-forget",
    )

    assert created.decision is Decision.ACCEPTED
    for rejected in (replay, later):
        assert rejected.decision is Decision.REJECTED
        assert rejected.effective_state is LifecycleState.FORGOTTEN
        assert rejected.error_code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE
