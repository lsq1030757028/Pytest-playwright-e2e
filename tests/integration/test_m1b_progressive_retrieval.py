from datetime import timedelta

import pytest

from test_workflow.memory_contracts import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    Decision,
    LifecycleState,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    PrincipalContext,
    PrincipalType,
    PromotionRequest,
    ReadMode,
    StateEvent,
    canonical_sha256,
)
from test_workflow.memory_store import (
    ProgressiveMemoryRetriever,
    RecallChannel,
    RetrievalRequest,
    RetrievalStage,
    RetrievalStatus,
    SQLiteDerivedIndex,
    SQLiteMemoryStore,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_owner,
    make_owner_acl,
    make_provenance,
    make_source_hash,
)

CURSOR_KEY = b"m1b-test-cursor-key-2026"


def make_store(path) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(
        path,
        resolved_sources={"requirement/REQ-1@3": make_source_hash()},
        resolved_evidence=("evidence/EV-1",),
        resolved_benchmarks=("benchmark/M1.0",),
        initial_acl=make_owner_acl(make_namespace()),
    )


def make_actor(project_id: str, principal_id: str) -> PrincipalContext:
    return PrincipalContext(
        principal_id=principal_id,
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id=project_id,
        agent_id=principal_id,
        role_ids=("OWNER", "VERIFIER", "PROMOTER", "PRIVACY_CONTROLLER"),
    )


def make_project_namespace(project_id: str) -> MemoryNamespace:
    return MemoryNamespace(
        organization_id="org-1",
        project_id=project_id,
        scope_kind=NamespaceScopeKind.PROJECT,
        scope_id=project_id,
    )


def make_revision(
    number: int,
    *,
    actor: PrincipalContext,
    namespace: MemoryNamespace,
    text: str,
) -> MemoryRevision:
    provenance = make_provenance().model_copy(
        update={"created_by_principal": actor.principal_id}
    )
    return MemoryRevision.create(
        memory_id=f"mem_{number:032x}",
        revision_nonce=f"retrieval-{number}",
        memory_kind=MemoryKind.SEMANTIC,
        namespace=namespace,
        content={"fact_candidate": text},
        provenance=provenance,
        retention_policy=make_retention(number),
        formation_event_ref=f"formation/retrieval-{number}",
        created_by=actor.principal_id,
        idempotency_key=f"idem-retrieval-{number}",
        created_at=FIXED_NOW + timedelta(seconds=number),
    )


def make_retention(number: int):
    from test_workflow.memory_contracts import RetentionPolicy

    return RetentionPolicy(
        policy_ref=f"retention/retrieval-{number}",
        review_after=FIXED_NOW + timedelta(days=30),
    )


def append_promoted(
    store: SQLiteMemoryStore,
    *,
    actor: PrincipalContext,
    revision: MemoryRevision,
) -> MemoryRevision:
    created = store.append_revision(
        actor=actor,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id=f"create-{revision.memory_id}",
    )
    assert created.decision is Decision.ACCEPTED
    verified = store.append_state_event(
        actor=actor,
        event=StateEvent.create(
            memory_id=revision.memory_id,
            revision_id=revision.revision_id,
            from_state=LifecycleState.CANDIDATE,
            to_state=LifecycleState.VERIFIED,
            reason_code="EVIDENCE_VERIFIED",
            actor_principal_ref=actor.principal_id,
            policy_decision_ref="policy/verify",
            occurred_at=revision.created_at + timedelta(milliseconds=100),
            nonce=f"verify-{revision.memory_id}",
        ),
        correlation_id=f"verify-{revision.memory_id}",
    )
    assert verified.effective_state is LifecycleState.VERIFIED
    promoted = store.promote(
        actor=actor,
        request=PromotionRequest(
            memory_id=revision.memory_id,
            revision_id=revision.revision_id,
            declared_promotion_scope=revision.namespace,
            evidence_refs=("evidence/EV-1",),
            benchmark_or_evaluator_refs=("benchmark/M1.0",),
            promoter_principal_ref=actor.principal_id,
            policy_decision_ref="policy/promote",
            compatibility=None,
            effective_from=revision.created_at + timedelta(milliseconds=200),
            rollback_or_disable_ref=f"rollback/{revision.memory_id}",
        ),
        correlation_id=f"promote-{revision.memory_id}",
    )
    assert promoted.effective_state is LifecycleState.PROMOTED
    return revision


def make_request(
    *,
    actor: PrincipalContext,
    namespace: MemoryNamespace,
    request_id: str,
    minimum_releases: int = 1,
    keywords: tuple[str, ...] = (),
    exact_refs: tuple[str, ...] = (),
    required_refs: tuple[str, ...] = (),
    cold_escalation_reason: str | None = None,
    cursor: str | None = None,
    vector_query_ref: str | None = None,
) -> RetrievalRequest:
    return RetrievalRequest(
        request_id=request_id,
        actor=actor,
        namespaces=(namespace,),
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        objective_ref=f"objective/{request_id}",
        objective_digest=canonical_sha256({"request": request_id}),
        evaluation_time=FIXED_NOW + timedelta(days=1),
        minimum_releases=minimum_releases,
        keywords=keywords,
        exact_refs=exact_refs,
        required_refs=required_refs,
        cold_escalation_reason=cold_escalation_reason,
        cursor=cursor,
        vector_query_ref=vector_query_ref,
    )


def test_authority_filter_happens_before_keyword_ranking(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    allowed = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            1,
            actor=actor,
            namespace=namespace,
            text="Playwright checkout timeout is 30 seconds",
        ),
    )
    unrelated = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            2,
            actor=actor,
            namespace=namespace,
            text="Redis retry policy uses bounded backoff",
        ),
    )

    other_actor = make_actor("project-2", "agent-project-2")
    other_namespace = make_project_namespace("project-2")
    secret = append_promoted(
        store,
        actor=other_actor,
        revision=make_revision(
            3,
            actor=other_actor,
            namespace=other_namespace,
            text="secret checkout timeout should never cross projects",
        ),
    )

    index = SQLiteDerivedIndex(db_path)
    assert index.apply_pending(limit=256) > 0
    assert index.contains_ref(secret.ref)

    result = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
    ).retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="authority-first",
            keywords=("checkout", "timeout"),
        )
    )

    assert result.status is RetrievalStatus.COMPLETE
    assert result.stage_reached is RetrievalStage.HOT
    assert result.released[0].ref == allowed.ref
    assert unrelated.ref in {item.ref for item in result.released}
    assert secret.ref not in {item.ref for item in result.released}
    assert result.budget.authorized_candidates == 2
    assert RecallChannel.KEYWORD in {
        item.channel for item in result.released[0].contributions
    }


def test_stale_index_cannot_release_forgotten_content(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    revision = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            10,
            actor=actor,
            namespace=namespace,
            text="forget barrier sensitive value",
        ),
    )
    index = SQLiteDerivedIndex(db_path)
    index.apply_pending(limit=256)
    assert index.contains_ref(revision.ref)

    revoked = store.revoke_memory(
        actor=actor,
        memory_id=revision.memory_id,
        reason_code="REQUIREMENT_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="revoke-forget-test",
    )
    assert revoked.effective_state is LifecycleState.REVOKED
    store.forget_memory(
        actor=actor,
        memory_id=revision.memory_id,
        reason_code="PRIVACY_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="forget-test",
    )

    assert index.contains_ref(revision.ref), "the test requires a deliberately stale index"
    retriever = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    )
    result = retriever.retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="stale-forget",
            exact_refs=(revision.ref,),
            required_refs=(revision.ref,),
        )
    )
    assert result.released == ()
    assert result.status in {
        RetrievalStatus.DEGRADED,
        RetrievalStatus.INSUFFICIENT_EVIDENCE,
    }
    assert "REQUIRED_REF_UNRESOLVED" in result.omitted_reasons

    index.apply_pending(limit=256)
    assert not index.contains_ref(revision.ref)


def test_hot_escalates_to_warm_only_when_coverage_requires_it(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    for number in range(20, 28):
        append_promoted(
            store,
            actor=actor,
            revision=make_revision(
                number,
                actor=actor,
                namespace=namespace,
                text=f"memory item {number} for warm coverage",
            ),
        )
    index = SQLiteDerivedIndex(db_path)
    index.apply_pending(limit=512)
    result = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
    ).retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="warm-coverage",
            minimum_releases=8,
        )
    )
    assert result.status is RetrievalStatus.COMPLETE
    assert result.stage_reached is RetrievalStage.WARM
    assert len(result.released) == 8


def test_cold_requires_explicit_reason_and_expands_cumulative_budget(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    for number in range(40, 53):
        append_promoted(
            store,
            actor=actor,
            revision=make_revision(
                number,
                actor=actor,
                namespace=namespace,
                text=f"historical memory item {number}",
            ),
        )
    index = SQLiteDerivedIndex(db_path)
    index.apply_pending(limit=1024)
    retriever = ProgressiveMemoryRetriever(store, index=index, cursor_key=CURSOR_KEY)

    limited = retriever.retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="cold-without-reason",
            minimum_releases=13,
        )
    )
    assert limited.stage_reached is RetrievalStage.WARM
    assert limited.status is RetrievalStatus.COMPLETE_WITH_LIMITS
    assert len(limited.released) == 12
    assert "COLD_ESCALATION_REASON_REQUIRED" in limited.omitted_reasons

    cold = retriever.retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="cold-with-reason",
            minimum_releases=13,
            cold_escalation_reason="coverage obligation requires historical context",
        )
    )
    assert cold.status is RetrievalStatus.COMPLETE
    assert cold.stage_reached is RetrievalStage.COLD
    assert len(cold.released) == 13
    assert any(
        contribution.channel is RecallChannel.ARCHIVE
        for released in cold.released
        for contribution in released.contributions
    )


def test_cursor_is_integrity_protected_and_bound_to_acl_epoch(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    for number in range(60, 70):
        append_promoted(
            store,
            actor=actor,
            revision=make_revision(
                number,
                actor=actor,
                namespace=namespace,
                text=f"paged memory {number}",
            ),
        )
    index = SQLiteDerivedIndex(db_path)
    index.apply_pending(limit=1024)
    retriever = ProgressiveMemoryRetriever(store, index=index, cursor_key=CURSOR_KEY)
    first_request = make_request(
        actor=actor,
        namespace=namespace,
        request_id="cursor-binding",
    )
    first = retriever.retrieve(first_request)
    assert len(first.released) == 6
    assert first.next_cursor is not None

    second = retriever.retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="cursor-binding",
            cursor=first.next_cursor,
        )
    )
    assert len(second.released) == 4
    assert {item.ref for item in first.released}.isdisjoint(
        {item.ref for item in second.released}
    )

    tampered = first.next_cursor[:-1] + (
        "A" if first.next_cursor[-1] != "A" else "B"
    )
    with pytest.raises(ValueError, match="cursor integrity"):
        retriever.retrieve(
            make_request(
                actor=actor,
                namespace=namespace,
                request_id="cursor-binding",
                cursor=tampered,
            )
        )

    store.append_acl_event(
        actor=actor,
        entry=AclEntry(
            rule_id="grant-cursor-reader",
            effect=AclEffect.ALLOW,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id="agent-cursor-reader",
            operations=(AccessOperation.READ_CONTENT,),
            namespace=namespace,
        ),
        correlation_id="acl-epoch-change",
    )
    with pytest.raises(ValueError, match="cursor binding mismatch: acl_epoch"):
        retriever.retrieve(
            make_request(
                actor=actor,
                namespace=namespace,
                request_id="cursor-binding",
                cursor=first.next_cursor,
            )
        )


def test_requested_unavailable_vector_channel_returns_declared_degraded_result(
    tmp_path,
) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            80,
            actor=actor,
            namespace=namespace,
            text="vector fallback memory",
        ),
    )
    index = SQLiteDerivedIndex(db_path)
    index.apply_pending(limit=256)
    result = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
    ).retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="vector-degraded",
            vector_query_ref="embedding/query@1",
        )
    )
    assert result.status is RetrievalStatus.DEGRADED
    assert result.stage_reached is RetrievalStage.WARM
    assert "VECTOR_UNAVAILABLE" in result.omitted_reasons
    assert len(result.released) == 1
