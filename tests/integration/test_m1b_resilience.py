import sqlite3

import pytest
from pydantic import ValidationError

from test_workflow.memory_contracts import ErrorCode, LifecycleState, MemoryContractError
from test_workflow.memory_store import ProgressiveMemoryRetriever, SQLiteDerivedIndex
from test_workflow.memory_store.resilience import (
    IndexHealthStatus,
    RetrievalReplayEvidence,
    RetrievalReplayVerifier,
    SQLiteIndexResilience,
)
from tests.integration.test_m1b_progressive_retrieval import (
    CURSOR_KEY,
    append_promoted,
    make_request,
    make_revision,
    make_store,
)
from tests.memory_contract_fixtures import make_namespace, make_owner


def _seed_two_memories(db_path):
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    first = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            201,
            actor=actor,
            namespace=namespace,
            text="playwright resilience memory alpha",
        ),
    )
    second = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            202,
            actor=actor,
            namespace=namespace,
            text="pytest resilience memory beta",
        ),
    )
    index = SQLiteDerivedIndex(db_path)
    while index.apply_pending(limit=256):
        pass
    return store, actor, namespace, first, second, index


def test_index_health_detects_missing_and_hash_corruption_then_rebuilds(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    _store, _actor, _namespace, first, second, index = _seed_two_memories(db_path)
    resilience = SQLiteIndexResilience(db_path)

    healthy = resilience.inspect()
    assert healthy.status is IndexHealthStatus.HEALTHY
    assert healthy.primary_revision_count == 2
    assert healthy.indexed_revision_count == 2

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DELETE FROM search_index WHERE memory_ref = ?",
            (first.ref,),
        )
        connection.commit()
    stale = resilience.inspect()
    assert stale.status is IndexHealthStatus.STALE
    assert stale.missing_refs == (first.ref,)

    rebuilt = resilience.rebuild()
    assert rebuilt.rebuilt_revision_count == 2
    assert resilience.inspect().status is IndexHealthStatus.HEALTHY
    assert index.contains_ref(first.ref)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE search_index SET content_hash = ? WHERE memory_ref = ?",
            ("0" * 64, second.ref),
        )
        connection.commit()
    corrupt = resilience.inspect()
    assert corrupt.status is IndexHealthStatus.CORRUPT
    assert corrupt.hash_mismatch_refs == (second.ref,)

    resilience.rebuild()
    assert resilience.inspect().status is IndexHealthStatus.HEALTHY


def test_forget_stale_index_is_detected_and_rebuild_cannot_resurrect(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store, actor, _namespace, first, _second, index = _seed_two_memories(db_path)
    assert index.contains_ref(first.ref)

    revoked = store.revoke_memory(
        actor=actor,
        memory_id=first.memory_id,
        reason_code="REQUIREMENT_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="resilience-revoke",
    )
    assert revoked.effective_state is LifecycleState.REVOKED
    store.forget_memory(
        actor=actor,
        memory_id=first.memory_id,
        reason_code="PRIVACY_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="resilience-forget",
    )

    # Deliberately do not consume the Forget outbox event. The stale index row
    # must be treated as corrupt because primary truth already forgot the content.
    assert index.contains_ref(first.ref)
    resilience = SQLiteIndexResilience(db_path)
    corrupt = resilience.inspect()
    assert corrupt.status is IndexHealthStatus.CORRUPT
    assert first.ref in corrupt.forgotten_refs

    resilience.rebuild()
    assert resilience.inspect().status is IndexHealthStatus.HEALTHY
    assert not index.contains_ref(first.ref)


def test_rebuild_preserves_deterministic_retrieval_replay(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store, actor, namespace, first, _second, index = _seed_two_memories(db_path)
    retriever = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    )
    request = make_request(
        actor=actor,
        namespace=namespace,
        request_id="resilience-replay",
        keywords=("playwright", "resilience"),
        required_refs=(first.ref,),
    )
    original = retriever.retrieve(request)
    evidence = RetrievalReplayEvidence.capture(request=request, result=original)

    with sqlite3.connect(db_path) as connection:
        connection.execute("DELETE FROM search_index")
        connection.commit()
    assert SQLiteIndexResilience(db_path).inspect().status is IndexHealthStatus.STALE
    SQLiteIndexResilience(db_path).rebuild()

    verification = RetrievalReplayVerifier(retriever).verify(
        request=request,
        evidence=evidence,
    )
    assert verification.equivalent is True
    assert verification.actual_manifest_digest == verification.expected_manifest_digest


def test_replay_evidence_and_request_tamper_are_rejected(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store, actor, namespace, first, _second, index = _seed_two_memories(db_path)
    retriever = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    )
    request = make_request(
        actor=actor,
        namespace=namespace,
        request_id="resilience-tamper",
        exact_refs=(first.ref,),
        required_refs=(first.ref,),
    )
    result = retriever.retrieve(request)
    evidence = RetrievalReplayEvidence.capture(request=request, result=result)

    tampered = evidence.model_dump(mode="json")
    tampered["released_hashes"] = ["0" * 64]
    with pytest.raises(ValidationError):
        RetrievalReplayEvidence.model_validate(tampered)

    changed_request = make_request(
        actor=actor,
        namespace=namespace,
        request_id="resilience-tamper-changed",
        exact_refs=(first.ref,),
        required_refs=(first.ref,),
    )
    with pytest.raises(MemoryContractError) as exc:
        RetrievalReplayVerifier(retriever).verify(
            request=changed_request,
            evidence=evidence,
        )
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
