import pytest

from test_workflow.memory_contracts import ErrorCode, LifecycleState, MemoryContractError
from test_workflow.memory_store import SQLiteMemoryStore
from test_workflow.memory_store.migration import SQLiteMigrationController
from tests.integration.test_m1b_progressive_retrieval import (
    append_promoted,
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

    controller = SQLiteMigrationController(source_path)
    report = controller.migrate(target_path)
    assert report.equivalent is True
    assert controller.cutover() == target_path
    assert controller.manifest(source_path).digest == controller.manifest(target_path).digest

    target_store = SQLiteMemoryStore(target_path)
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
