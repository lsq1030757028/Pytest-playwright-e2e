from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryAclPort,
    MemoryAuditPort,
    MemoryContractError,
    MemoryMaintenancePort,
    MemoryQueryPort,
    MemoryRevision,
    MemoryRevisionPort,
    MemoryStatePort,
    PromotionRequest,
    StateEvent,
)
from test_workflow.memory_store import SQLiteMemoryStore
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_owner,
    make_owner_acl,
    make_semantic_revision,
    make_source_hash,
)


def make_store(path):
    return SQLiteMemoryStore(
        path,
        resolved_sources={"requirement/REQ-1@3": make_source_hash()},
        resolved_evidence=("evidence/EV-1",),
        resolved_benchmarks=("benchmark/M1.0",),
        initial_acl=make_owner_acl(make_namespace()),
    )


def make_second_revision(
    initial: MemoryRevision, *, nonce: str, key: str, value: str
) -> MemoryRevision:
    owner = make_owner()
    return MemoryRevision.create(
        memory_id=initial.memory_id,
        revision_nonce=nonce,
        revision_number=2,
        parent_revision_refs=(initial.ref,),
        memory_kind=initial.memory_kind,
        namespace=initial.namespace,
        content={"fact_candidate": value},
        provenance=initial.provenance,
        retention_policy=initial.retention_policy,
        formation_event_ref=f"formation/{nonce}",
        created_by=owner.principal_id,
        idempotency_key=key,
        created_at=initial.created_at + timedelta(minutes=1),
    )


def test_sqlite_store_uses_wal_and_implements_all_m1a_ports(tmp_path) -> None:
    store = make_store(tmp_path / "memory.db")
    assert store.journal_mode() == "wal"
    assert isinstance(store, MemoryRevisionPort)
    assert isinstance(store, MemoryStatePort)
    assert isinstance(store, MemoryAclPort)
    assert isinstance(store, MemoryQueryPort)
    assert isinstance(store, MemoryAuditPort)
    assert isinstance(store, MemoryMaintenancePort)


def test_revision_and_idempotency_survive_restart(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    revision = make_semantic_revision()
    owner = make_owner()

    first = make_store(db_path)
    created = first.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    assert created.decision is Decision.ACCEPTED
    assert [event["event_type"] for event in first.pending_outbox()] == [
        "REVISION_COMMITTED"
    ]

    restarted = make_store(db_path)
    assert restarted.get_head_revision(
        actor=owner, memory_id=revision.memory_id
    ) == revision
    replayed = restarted.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="replay-after-restart",
    )
    assert replayed == created
    assert restarted.verify_event_chain()

    changed_actor = owner.model_copy(
        update={"principal_id": "agent-other", "agent_id": "agent-other"}
    )
    with pytest.raises(MemoryContractError) as exc:
        restarted.append_revision(
            actor=changed_actor,
            revision=revision,
            expected_head_revision_id=None,
            correlation_id="changed-actor",
        )
    assert exc.value.code is ErrorCode.DUPLICATE_IDEMPOTENCY_KEY


def test_head_cas_and_state_survive_restart(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    initial = make_semantic_revision()
    owner = make_owner()
    store = make_store(db_path)
    store.append_revision(
        actor=owner,
        revision=initial,
        expected_head_revision_id=None,
        correlation_id="initial",
    )
    second = make_second_revision(
        initial,
        nonce="second",
        key="idem-second",
        value="The approved timeout is 45 seconds.",
    )
    accepted = store.compare_and_append_revision(
        actor=owner,
        revision=second,
        expected_head_revision_id=initial.revision_id,
        correlation_id="second",
    )
    verify_event = StateEvent.create(
        memory_id=initial.memory_id,
        revision_id=second.revision_id,
        from_state=LifecycleState.CANDIDATE,
        to_state=LifecycleState.VERIFIED,
        reason_code="EVIDENCE_VERIFIED",
        actor_principal_ref=owner.principal_id,
        policy_decision_ref="policy/verify",
        occurred_at=FIXED_NOW + timedelta(minutes=2),
        nonce="verify-second",
    )
    verified = store.append_state_event(
        actor=owner, event=verify_event, correlation_id="verify"
    )

    restarted = make_store(db_path)
    assert accepted.decision is Decision.ACCEPTED
    assert verified.effective_state is LifecycleState.VERIFIED
    assert restarted.get_head_revision(
        actor=owner, memory_id=initial.memory_id
    ).revision_id == second.revision_id
    assert restarted.get_effective_state(
        memory_id=initial.memory_id
    ) is LifecycleState.VERIFIED
    assert restarted.verify_event_chain()


def test_two_process_like_instances_have_one_cas_winner(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    initial = make_semantic_revision()
    owner = make_owner()
    bootstrap = make_store(db_path)
    bootstrap.append_revision(
        actor=owner,
        revision=initial,
        expected_head_revision_id=None,
        correlation_id="base",
    )
    candidates = (
        make_second_revision(
            initial, nonce="concurrent-a", key="idem-a", value="candidate A"
        ),
        make_second_revision(
            initial, nonce="concurrent-b", key="idem-b", value="candidate B"
        ),
    )
    stores = (make_store(db_path), make_store(db_path))
    barrier = Barrier(2)

    def append(item):
        store, revision = item
        barrier.wait()
        return store.compare_and_append_revision(
            actor=owner,
            revision=revision,
            expected_head_revision_id=initial.revision_id,
            correlation_id=revision.idempotency_key,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(append, zip(stores, candidates, strict=True)))

    assert sorted(result.decision.value for result in results) == [
        Decision.ACCEPTED.value,
        Decision.CONFLICT.value,
    ]
    restarted = make_store(db_path)
    assert len(
        restarted.list_revision_history(actor=owner, memory_id=initial.memory_id)
    ) == 2
    assert restarted.verify_event_chain()


def test_acl_audit_and_outbox_survive_restart(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    owner = make_owner()
    namespace = make_namespace()
    store = make_store(db_path)
    grant = AclEntry(
        rule_id="grant-reader",
        effect=AclEffect.ALLOW,
        subject_type=AclSubjectType.PRINCIPAL,
        subject_id="agent-reader",
        operations=(AccessOperation.READ_CONTENT,),
        namespace=namespace,
    )
    result = store.append_acl_event(
        actor=owner,
        entry=grant,
        correlation_id="grant-reader",
    )
    assert result.decision is Decision.ACCEPTED

    restarted = make_store(db_path)
    assert grant in restarted.list_effective_acl(namespace=namespace)
    assert restarted.list_audit_events()[-1].event_type == "ACL_CHANGED"
    assert restarted.verify_event_chain()
    assert "ACL_COMMITTED" in {
        event["event_type"] for event in restarted.pending_outbox()
    }


def test_forget_removes_primary_content_and_blocks_resurrection_after_restart(
    tmp_path,
) -> None:
    db_path = tmp_path / "memory.db"
    revision = make_semantic_revision()
    owner = make_owner()
    store = make_store(db_path)
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    verified = store.append_state_event(
        actor=owner,
        event=StateEvent.create(
            memory_id=revision.memory_id,
            revision_id=revision.revision_id,
            from_state=LifecycleState.CANDIDATE,
            to_state=LifecycleState.VERIFIED,
            reason_code="EVIDENCE_VERIFIED",
            actor_principal_ref=owner.principal_id,
            policy_decision_ref="policy/verify",
            occurred_at=FIXED_NOW,
            nonce="verify",
        ),
        correlation_id="verify",
    )
    assert verified.effective_state is LifecycleState.VERIFIED
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
            rollback_or_disable_ref="rollback/promotion-1",
        ),
        correlation_id="promote",
    )
    assert promoted.effective_state is LifecycleState.PROMOTED
    revoked = store.revoke_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="REQUIREMENT_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="revoke",
    )
    assert revoked.effective_state is LifecycleState.REVOKED
    tombstone = store.forget_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="PRIVACY_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="forget",
    )

    assert tombstone.memory_id == revision.memory_id
    assert store.primary_content_rows(memory_id=revision.memory_id) == 0

    restarted = make_store(db_path)
    assert restarted.get_tombstone(memory_id=revision.memory_id) == tombstone
    assert restarted.primary_content_rows(memory_id=revision.memory_id) == 0
    assert restarted.verify_cache_and_index_invalidation(memory_id=revision.memory_id)
    assert restarted.verify_event_chain()
    with pytest.raises(MemoryContractError) as exc:
        restarted.get_head_revision(actor=owner, memory_id=revision.memory_id)
    assert exc.value.code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE

    replay_attempt = restarted.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="no-resurrection",
    )
    assert replay_attempt.decision is Decision.REJECTED
    assert replay_attempt.error_code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE
    assert restarted.primary_content_rows(memory_id=revision.memory_id) == 0
    assert "FORGET_COMMITTED" in {
        event["event_type"] for event in restarted.pending_outbox()
    }
