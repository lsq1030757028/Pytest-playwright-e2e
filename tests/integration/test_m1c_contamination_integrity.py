import sqlite3

import pytest

from test_workflow.memory_contracts import (
    ErrorCode,
    MemoryContractError,
    canonical_sha256,
)
from test_workflow.memory_formation import (
    BackgroundConsolidator,
    ConsolidationStatus,
    FormationRuntime,
    FormationStatus,
)
from test_workflow.memory_formation.contamination import (
    ContaminationClass,
    MemoryContaminationRegistry,
)
from test_workflow.memory_store import SQLiteMemoryStore
from tests.integration.test_m1c_background_consolidation import _hot_parent, _request
from tests.integration.test_m1c_hot_formation import make_artifacts, make_request


def test_contaminated_parent_is_rejected_before_corrupted_content_parse(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="fixture answer 42", number=902)
    registry = MemoryContaminationRegistry(db_path)
    registry.mark(
        memory_ref=parent,
        contamination_class=ContaminationClass.HIDDEN_HOLDOUT,
        evidence_digest=canonical_sha256({"fixture": "hidden-902"}),
    )
    _memory_id, revision_id = parent.split("@", 1)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE revisions SET payload_json = 'not-json' WHERE revision_id = ?",
            (revision_id,),
        )
        connection.commit()

    result = BackgroundConsolidator(SQLiteMemoryStore(db_path)).consolidate(
        _request(
            parents=(parent,),
            claim="fixture answer 42",
            subject="holdout-cleaning",
            request_id="holdout-cleaning",
            idempotency_key="holdout-cleaning-idem",
        )
    )

    assert result.status is ConsolidationStatus.REJECTED
    assert result.rejected_reasons == ("PARENT_CONTAMINATED",)
    assert result.candidate_revision_ref is None


def test_late_contamination_mark_propagates_to_existing_descendants(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=903)
    consolidator = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    child = consolidator.consolidate(
        _request(
            parents=(parent,),
            subject="preexisting-descendant",
            request_id="preexisting-descendant",
            idempotency_key="preexisting-descendant-idem",
        )
    )
    assert child.status is ConsolidationStatus.CREATED_CANDIDATE

    registry = MemoryContaminationRegistry(db_path)
    registry.mark(
        memory_ref=parent,
        contamination_class=ContaminationClass.EVALUATOR_ONLY,
        evidence_digest=canonical_sha256({"evaluator": "later-discovered"}),
    )
    assert registry.is_contaminated(parent)
    assert registry.is_contaminated(child.candidate_revision_ref)

    grandchild = BackgroundConsolidator(SQLiteMemoryStore(db_path)).consolidate(
        _request(
            parents=(child.candidate_revision_ref,),
            subject="contaminated-grandchild",
            request_id="contaminated-grandchild",
            idempotency_key="contaminated-grandchild-idem",
        )
    )
    assert grandchild.status is ConsolidationStatus.REJECTED
    assert grandchild.rejected_reasons == ("PARENT_CONTAMINATED",)


def test_nested_authority_override_payload_is_rejected(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=904)
    result = BackgroundConsolidator(SQLiteMemoryStore(db_path)).consolidate(
        _request(
            parents=(parent,),
            candidate_content={
                "claim": "timeout is 30 seconds",
                "metadata": {"permission_override": "ALLOW_PRODUCTION"},
            },
            subject="nested-authority-override",
            request_id="nested-authority-override",
            idempotency_key="nested-authority-override-idem",
        )
    )

    assert result.status is ConsolidationStatus.REJECTED
    assert result.rejected_reasons == ("PROTECTED_AUTHORITY_MUTATION_ATTEMPT",)


def test_tampered_formation_event_blocks_subsequent_formation(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    artifacts, source, evidence = make_artifacts()
    runtime = FormationRuntime(SQLiteMemoryStore(db_path), artifacts)
    first = runtime.form(make_request(source=source, evidence=evidence))
    assert first.status is FormationStatus.CREATED_CANDIDATE

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE formation_events SET event_hash = ?",
            ("0" * 64,),
        )
        connection.commit()

    second_request = make_request(
        source=source,
        evidence=evidence,
        request_id="after-event-tamper",
        idempotency_key="after-event-tamper-idem",
        semantic_subject_key="after-event-tamper",
    )
    with pytest.raises(MemoryContractError) as exc:
        runtime.form(second_request)
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED


def test_tampered_consolidation_replay_blocks_subsequent_consolidation(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=905)
    consolidator = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    first = consolidator.consolidate(
        _request(
            parents=(parent,),
            subject="tamper-source",
            request_id="tamper-source",
            idempotency_key="tamper-source-idem",
        )
    )
    assert first.status is ConsolidationStatus.CREATED_CANDIDATE

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE consolidation_replay SET payload_json = '{}'")
        connection.commit()

    with pytest.raises(MemoryContractError) as exc:
        consolidator.consolidate(
            _request(
                parents=(parent,),
                subject="after-replay-tamper",
                request_id="after-replay-tamper",
                idempotency_key="after-replay-tamper-idem",
            )
        )
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
