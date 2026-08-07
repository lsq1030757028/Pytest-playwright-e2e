import sqlite3

import pytest

from test_workflow.memory_contracts import ErrorCode, MemoryContractError, canonical_sha256
from test_workflow.memory_formation import (
    BackgroundConsolidator,
    ConsolidationStatus,
    FormationRuntime,
    FormationStatus,
    verify_formation_integrity,
)
from test_workflow.memory_formation.contamination import (
    ContaminationClass,
    MemoryContaminationRegistry,
)
from test_workflow.memory_store import SQLiteMemoryStore, SQLiteMigrationController
from tests.integration.test_m1c_background_consolidation import _request
from tests.integration.test_m1c_hot_formation import make_artifacts, make_request


def _m1c_source(db_path):
    artifacts, source, evidence = make_artifacts()
    hot_runtime = FormationRuntime(SQLiteMemoryStore(db_path), artifacts)
    hot_request = make_request(
        source=source,
        evidence=evidence,
        request_id="migration-hot",
        idempotency_key="migration-hot-idem",
        semantic_subject_key="migration-hot-subject",
    )
    hot_result = hot_runtime.form(hot_request)
    assert hot_result.status is FormationStatus.CREATED_CANDIDATE

    consolidation_request = _request(
        parents=(hot_result.candidate_revision_ref,),
        subject="migration-derived-subject",
        request_id="migration-derived",
        idempotency_key="migration-derived-idem",
    )
    consolidation_runtime = BackgroundConsolidator(SQLiteMemoryStore(db_path))
    consolidation_result = consolidation_runtime.consolidate(consolidation_request)
    assert consolidation_result.status is ConsolidationStatus.CREATED_CANDIDATE

    registry = MemoryContaminationRegistry(db_path)
    registry.mark(
        memory_ref=hot_result.candidate_revision_ref,
        contamination_class=ContaminationClass.EVALUATOR_ONLY,
        evidence_digest=canonical_sha256({"fixture": "migration-evaluator"}),
    )
    assert registry.is_contaminated(hot_result.candidate_revision_ref)
    assert registry.is_contaminated(consolidation_result.candidate_revision_ref)

    return (
        artifacts,
        hot_request,
        hot_result,
        consolidation_request,
        consolidation_result,
    )


def test_migration_manifest_covers_all_m1c_durable_surfaces(tmp_path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    (
        artifacts,
        hot_request,
        hot_result,
        consolidation_request,
        consolidation_result,
    ) = _m1c_source(source_path)

    controller = SQLiteMigrationController(source_path)
    source_manifest = controller.manifest(source_path)
    assert source_manifest.formation_event_digests
    assert source_manifest.formation_idempotency_digests
    assert source_manifest.formation_replay_digests
    assert source_manifest.consolidation_event_digests
    assert source_manifest.consolidation_idempotency_digests
    assert source_manifest.consolidation_replay_digests
    assert source_manifest.contamination_record_digests
    assert source_manifest.contamination_checkpoint_digests

    report = controller.migrate(target_path)

    assert report.equivalent is True
    target_manifest = controller.manifest(target_path)
    assert target_manifest.digest == source_manifest.digest
    verify_formation_integrity(target_path)

    target_hot = FormationRuntime(SQLiteMemoryStore(target_path), artifacts)
    assert target_hot.replay_evidence(hot_request.request_digest).manifest_digest == (
        hot_result.replay_evidence_digest
    )
    target_consolidator = BackgroundConsolidator(SQLiteMemoryStore(target_path))
    assert target_consolidator.replay_evidence(
        consolidation_request.request_digest
    ).manifest_digest == consolidation_result.replay_evidence_digest
    target_registry = MemoryContaminationRegistry(target_path)
    assert target_registry.is_contaminated(hot_result.candidate_revision_ref)
    assert target_registry.is_contaminated(consolidation_result.candidate_revision_ref)

    assert controller.cutover() == target_path
    assert controller.rollback() == source_path


def test_cutover_rejects_target_missing_completed_m1c_replay(tmp_path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    _artifacts, _hot_request, _hot_result, consolidation_request, _result = _m1c_source(
        source_path
    )
    controller = SQLiteMigrationController(source_path)
    assert controller.migrate(target_path).equivalent is True

    with sqlite3.connect(target_path) as connection:
        connection.execute(
            "DELETE FROM consolidation_replay WHERE request_digest = ?",
            (consolidation_request.request_digest,),
        )
        connection.commit()

    with pytest.raises(MemoryContractError) as exc:
        controller.cutover()
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
    assert controller.active_path == source_path


def test_cutover_rejects_target_missing_m1c_idempotency_even_when_links_validate(
    tmp_path,
) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    _m1c_source(source_path)
    controller = SQLiteMigrationController(source_path)
    assert controller.migrate(target_path).equivalent is True

    with sqlite3.connect(target_path) as connection:
        connection.execute("DELETE FROM formation_idempotency")
        connection.commit()

    # Event/replay payloads can still be individually valid, but the canonical
    # migration manifest must detect that authenticated Formation state vanished.
    verify_formation_integrity(target_path)
    with pytest.raises(MemoryContractError) as exc:
        controller.cutover()
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
    assert controller.active_path == source_path
