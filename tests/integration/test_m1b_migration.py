import pytest

from test_workflow.memory_contracts import ErrorCode, LifecycleState, MemoryContractError
from test_workflow.memory_store import (
    ProgressiveMemoryRetriever,
    SQLiteDerivedIndex,
    SQLiteMemoryStore,
)
from test_workflow.memory_store.migration import SQLiteMigrationController
from tests.integration.test_m1b_progressive_retrieval import (
    CURSOR_KEY,
    append_promoted,
    make_request,
    make_revision,
    make_store,
)
from tests.memory_contract_fixtures import make_namespace, make_owner


def test_manifest_verified_cutover_and_safe_rollback(tmp_path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    store = make_store(source_path)
    actor = make_owner()
    namespace = make_namespace()
    live = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            401,
            actor=actor,
            namespace=namespace,
            text="migration live memory",
        ),
    )
    forgotten = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            402,
            actor=actor,
            namespace=namespace,
            text="migration forgotten memory",
        ),
    )
    store.revoke_memory(
        actor=actor,
        memory_id=forgotten.memory_id,
        reason_code="REQUIREMENT_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="migration-revoke",
    )
    store.forget_memory(
        actor=actor,
        memory_id=forgotten.memory_id,
        reason_code="PRIVACY_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="migration-forget",
    )
    source_index = SQLiteDerivedIndex(source_path)
    while source_index.apply_pending(limit=256):
        pass
    request = make_request(
        actor=actor,
        namespace=namespace,
        request_id="migration-shadow-read",
        exact_refs=(live.ref,),
        required_refs=(live.ref,),
    )
    source_result = ProgressiveMemoryRetriever(
        store,
        index=source_index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    ).retrieve(request)

    controller = SQLiteMigrationController(source_path)
    report = controller.migrate(target_path)
    assert report.equivalent is True
    assert controller.manifest(source_path).digest == controller.manifest(target_path).digest

    target_store = SQLiteMemoryStore(target_path)
    target_result = ProgressiveMemoryRetriever(
        target_store,
        index=SQLiteDerivedIndex(target_path),
        cursor_key=CURSOR_KEY,
        sync_index=False,
    ).retrieve(request)
    assert [item.ref for item in target_result.released] == [
        item.ref for item in source_result.released
    ]
    assert [item.content_hash for item in target_result.released] == [
        item.content_hash for item in source_result.released
    ]
    assert target_result.evidence_digest == source_result.evidence_digest

    assert controller.cutover() == target_path
    assert target_store.get_tombstone(memory_id=forgotten.memory_id) is not None
    assert target_store.get_head_revision(actor=actor, memory_id=live.memory_id).ref == live.ref

    assert controller.rollback() == source_path


def test_rollback_is_blocked_after_target_only_forget(tmp_path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    store = make_store(source_path)
    actor = make_owner()
    namespace = make_namespace()
    live = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            403,
            actor=actor,
            namespace=namespace,
            text="rollback must not resurrect target-only forget",
        ),
    )

    controller = SQLiteMigrationController(source_path)
    assert controller.migrate(target_path).equivalent is True
    assert controller.cutover() == target_path

    target_store = SQLiteMemoryStore(target_path)
    revoked = target_store.revoke_memory(
        actor=actor,
        memory_id=live.memory_id,
        reason_code="TARGET_REVOKED",
        policy_decision_ref="policy/revoke",
        correlation_id="target-revoke",
    )
    assert revoked.effective_state is LifecycleState.REVOKED
    target_store.forget_memory(
        actor=actor,
        memory_id=live.memory_id,
        reason_code="TARGET_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="target-forget",
    )

    with pytest.raises(MemoryContractError) as exc:
        controller.rollback()
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
    assert controller.active_path == target_path
