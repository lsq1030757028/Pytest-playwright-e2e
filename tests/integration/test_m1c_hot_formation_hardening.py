import sqlite3

from test_workflow.memory_formation import FormationRuntime, FormationStatus, SourceClass
from test_workflow.memory_store import SQLiteMemoryStore
from tests.integration.test_m1b_progressive_retrieval import make_actor
from tests.integration.test_m1c_hot_formation import (
    make_artifacts,
    make_request,
    make_runtime,
)


class SpyArtifactStore:
    def __init__(self) -> None:
        self.get_calls = 0

    def put(self, **kwargs):
        raise AssertionError("formation hardening spy is read-only")

    def get(self, ref):
        self.get_calls += 1
        raise AssertionError("artifact content must not be read before target authority")


def test_target_authority_is_denied_before_any_artifact_read(tmp_path) -> None:
    artifacts, source, evidence = make_artifacts()
    db_path, store, _runtime = make_runtime(tmp_path, artifacts)
    spy = SpyArtifactStore()
    runtime = FormationRuntime(store, spy)
    request = make_request(source=source, evidence=evidence).model_copy(
        update={
            "actor": make_actor("project-2", "agent-unauthorized-formation"),
            "request_id": "authority-before-source-read",
            "idempotency_key": "authority-before-source-read-idem",
        }
    )

    result = runtime.form(request)

    assert result.status is FormationStatus.REJECTED
    assert result.rejected_reasons == ("TARGET_NAMESPACE_APPEND_DENIED",)
    assert spy.get_calls == 0
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0


def test_retry_after_result_loss_reuses_same_candidate_without_second_revision(tmp_path) -> None:
    artifacts, source, evidence = make_artifacts()
    db_path, _store, runtime = make_runtime(tmp_path, artifacts)
    request = make_request(source=source, evidence=evidence)
    first = runtime.form(request)
    assert first.status is FormationStatus.CREATED_CANDIDATE
    memory_id, _revision_id = first.candidate_revision_ref.split("@", 1)

    # Simulate the crash window after the governed M1B Candidate commit but
    # before FormationResult durability. The reservation survives as IN_PROGRESS.
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE formation_idempotency
            SET state = 'IN_PROGRESS', result_json = NULL
            WHERE idempotency_key = ?
            """,
            (request.idempotency_key,),
        )
        connection.execute(
            "DELETE FROM formation_replay WHERE request_digest = ?",
            (request.request_digest,),
        )
        connection.commit()

    restarted_runtime = FormationRuntime(SQLiteMemoryStore(db_path), artifacts)
    recovered = restarted_runtime.form(request)

    assert recovered.status is FormationStatus.DUPLICATE_SUPPRESSED
    assert recovered.candidate_revision_ref == first.candidate_revision_ref
    store = SQLiteMemoryStore(db_path)
    assert len(store.list_revision_history(actor=request.actor, memory_id=memory_id)) == 1
    assert restarted_runtime.form(request) == recovered
    assert restarted_runtime.replay_evidence(request.request_digest).manifest_digest == (
        recovered.replay_evidence_digest
    )


def test_current_requirement_source_must_be_bound_to_authority_refs(tmp_path) -> None:
    artifacts, source, evidence = make_artifacts(
        source_content={"requirement": "timeout is 30 seconds"}
    )
    _db_path, _store, runtime = make_runtime(tmp_path, artifacts)
    request = make_request(
        source=source,
        evidence=evidence,
        request_id="requirement-unbound",
        idempotency_key="requirement-unbound-idem",
    )
    requirement_source = request.sources[0].model_copy(
        update={"source_class": SourceClass.REQUIREMENT_REVISION}
    )
    request = request.model_copy(
        update={
            "sources": (requirement_source,),
            "supporting_source_refs": (requirement_source.source_ref,),
            "authority_refs": ("requirement/current-other@2",),
        }
    )

    result = runtime.form(request)

    assert result.status is FormationStatus.REJECTED
    assert result.rejected_reasons == ("CURRENT_REQUIREMENT_AUTHORITY_UNBOUND",)


def test_tampered_artifact_hash_is_rejected_by_artifact_store_resolution(tmp_path) -> None:
    artifacts, source, evidence = make_artifacts()
    _db_path, _store, runtime = make_runtime(tmp_path, artifacts)
    tampered_ref = source.model_copy(update={"content_hash": "sha256:" + "0" * 64})
    request = make_request(
        source=tampered_ref,
        evidence=evidence,
        request_id="tampered-source-hash",
        idempotency_key="tampered-source-hash-idem",
    )

    result = runtime.form(request)

    assert result.status is FormationStatus.REJECTED
    assert result.rejected_reasons == ("SOURCE_ARTIFACT_UNRESOLVED",)
