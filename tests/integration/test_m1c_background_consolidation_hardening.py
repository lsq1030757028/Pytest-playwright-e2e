import sqlite3

from test_workflow.memory_formation import BackgroundConsolidator, ConsolidationStatus
from test_workflow.memory_store import SQLiteMemoryStore
from tests.integration.test_m1b_progressive_retrieval import make_actor
from tests.integration.test_m1c_background_consolidation import _hot_parent, _request


def test_retry_after_result_loss_does_not_create_second_derived_revision(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=701)
    request = _request(
        parents=(parent,),
        subject="retry-after-result-loss",
        request_id="retry-after-result-loss",
        idempotency_key="retry-after-result-loss-idem",
    )
    consolidator = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    first = consolidator.consolidate(request)
    assert first.status is ConsolidationStatus.CREATED_CANDIDATE
    memory_id, _revision_id = first.candidate_revision_ref.split("@", 1)

    # Simulate the crash window after the governed M1B Candidate commit but
    # before the I2 result/replay durability boundary completes.
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE consolidation_idempotency
            SET state = 'IN_PROGRESS', result_json = NULL
            WHERE idempotency_key = ?
            """,
            (request.idempotency_key,),
        )
        connection.execute(
            "DELETE FROM consolidation_replay WHERE request_digest = ?",
            (request.request_digest,),
        )
        connection.commit()

    restarted = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    recovered = restarted.consolidate(request)

    assert recovered.status is ConsolidationStatus.DUPLICATE_SUPPRESSED
    assert recovered.candidate_revision_ref == first.candidate_revision_ref
    store = SQLiteMemoryStore(db_path)
    assert len(store.list_revision_history(actor=request.actor, memory_id=memory_id)) == 1
    assert restarted.consolidate(request) == recovered
    assert restarted.replay_evidence(request.request_digest).manifest_digest == (
        recovered.replay_evidence_digest
    )


def test_unauthorized_actor_cannot_squat_consolidation_idempotency_key(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=702)
    authorized = _request(
        parents=(parent,),
        subject="authority-before-consolidation-reservation",
        request_id="authorized-consolidation",
        idempotency_key="shared-consolidation-idem",
    )
    unauthorized = authorized.model_copy(
        update={"actor": make_actor("project-2", "agent-unauthorized-consolidator")}
    )
    consolidator = BackgroundConsolidator(SQLiteMemoryStore(db_path))

    denied = consolidator.consolidate(unauthorized)

    assert denied.status is ConsolidationStatus.REJECTED
    assert denied.rejected_reasons == ("TARGET_NAMESPACE_AUTHORITY_DENIED",)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM consolidation_idempotency"
        ).fetchone()[0] == 0

    accepted = consolidator.consolidate(authorized)
    assert accepted.status is ConsolidationStatus.CREATED_CANDIDATE


def test_fabricated_requirement_authority_ref_cannot_form_candidate(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=703)
    request = _request(
        parents=(parent,),
        subject="fabricated-authority",
        request_id="fabricated-authority",
        idempotency_key="fabricated-authority-idem",
    ).model_copy(update={"authority_refs": ("requirement/fabricated@999",)})
    consolidator = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    with sqlite3.connect(db_path) as connection:
        before = connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]

    result = consolidator.consolidate(request)

    assert result.status is ConsolidationStatus.REJECTED
    assert result.candidate_revision_ref is None
    with sqlite3.connect(db_path) as connection:
        after = connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
    assert after == before
