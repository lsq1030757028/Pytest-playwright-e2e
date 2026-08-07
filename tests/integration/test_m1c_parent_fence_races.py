from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

from test_workflow.memory_contracts import Decision, MemoryRevision
from test_workflow.memory_formation import BackgroundConsolidator, ConsolidationStatus
from test_workflow.memory_store import SQLiteMemoryStore
from tests.integration.test_m1c_background_consolidation import _hot_parent, _request
from tests.memory_contract_fixtures import make_owner


class PauseAfterRevalidateConsolidator(BackgroundConsolidator):
    def __init__(self, store, *, reached: Event, resume: Event) -> None:
        super().__init__(store)
        self.reached = reached
        self.resume = resume

    def _revalidate(self, request, parents):
        valid = super()._revalidate(request, parents)
        self.reached.set()
        if not self.resume.wait(timeout=10):
            raise TimeoutError("parent fence race did not resume")
        return valid


def _run_paused(consolidator, request, mutate) -> object:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(consolidator.consolidate, request)
        assert consolidator.reached.wait(timeout=10)
        mutate()
        consolidator.resume.set()
        return future.result(timeout=10)


def _append_new_parent_head(db_path, parent_ref: str, *, nonce: str) -> None:
    actor = make_owner()
    memory_id, _revision_id = parent_ref.split("@", 1)
    reader = SQLiteMemoryStore(db_path)
    head = reader.get_head_revision(actor=actor, memory_id=memory_id)
    mutator = SQLiteMemoryStore(
        db_path,
        resolved_sources=dict(head.provenance.source_content_hashes),
        resolved_evidence=head.provenance.evidence_refs,
    )
    content = dict(head.content)
    content["race_marker"] = nonce
    revision = MemoryRevision.create(
        memory_id=head.memory_id,
        revision_nonce=nonce,
        revision_number=head.revision_number + 1,
        parent_revision_refs=(head.ref,),
        memory_kind=head.memory_kind,
        namespace=head.namespace,
        content=content,
        provenance=head.provenance,
        retention_policy=head.retention_policy,
        formation_event_ref=f"formation/{nonce}",
        created_by=actor.principal_id,
        idempotency_key=f"idem-{nonce}",
        created_at=head.created_at + timedelta(seconds=1),
    )
    result = mutator.append_revision(
        actor=actor,
        revision=revision,
        expected_head_revision_id=head.revision_id,
        correlation_id=f"race/{nonce}",
    )
    assert result.decision is Decision.ACCEPTED


def test_parent_head_change_after_revalidation_blocks_derived_commit(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=801)
    request = _request(
        parents=(parent,),
        subject="head-race-target",
        request_id="head-race",
        idempotency_key="head-race-idem",
    )
    reached, resume = Event(), Event()
    consolidator = PauseAfterRevalidateConsolidator(
        SQLiteMemoryStore(db_path), reached=reached, resume=resume
    )

    result = _run_paused(
        consolidator,
        request,
        lambda: _append_new_parent_head(db_path, parent, nonce="parent-head-race"),
    )

    assert result.status is ConsolidationStatus.REJECTED
    assert result.rejected_reasons == ("REVISION_CONFLICT",)
    assert result.candidate_revision_ref is None
    target_id = consolidator._memory_id(request)
    assert SQLiteMemoryStore(db_path).primary_content_rows(memory_id=target_id) == 0


def test_parent_forget_after_revalidation_blocks_derived_commit(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _hot_parent(db_path, claim="timeout is 30 seconds", number=802)
    request = _request(
        parents=(parent,),
        subject="forget-race-target",
        request_id="forget-race",
        idempotency_key="forget-race-idem",
    )
    reached, resume = Event(), Event()
    consolidator = PauseAfterRevalidateConsolidator(
        SQLiteMemoryStore(db_path), reached=reached, resume=resume
    )
    parent_id, _revision_id = parent.split("@", 1)

    def forget_parent() -> None:
        mutator = SQLiteMemoryStore(db_path)
        mutator.revoke_memory(
            actor=make_owner(),
            memory_id=parent_id,
            reason_code="I3_RACE_REVOKE",
            policy_decision_ref="policy/race-revoke",
            correlation_id="i3-race-revoke",
        )
        mutator.forget_memory(
            actor=make_owner(),
            memory_id=parent_id,
            reason_code="I3_RACE_FORGET",
            policy_decision_ref="policy/race-forget",
            correlation_id="i3-race-forget",
        )

    result = _run_paused(consolidator, request, forget_parent)

    assert result.status is ConsolidationStatus.REJECTED
    assert result.rejected_reasons == ("FORGOTTEN_CONTENT_UNAVAILABLE",)
    assert result.candidate_revision_ref is None
    target_id = consolidator._memory_id(request)
    assert SQLiteMemoryStore(db_path).primary_content_rows(memory_id=target_id) == 0


def test_parent_revoke_after_revalidation_is_blocked_across_100_races(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    actor = make_owner()

    for repetition in range(100):
        parent = _hot_parent(
            db_path,
            claim=f"race fact {repetition}",
            number=9_000 + repetition,
        )
        request = _request(
            parents=(parent,),
            claim=f"race fact {repetition}",
            subject=f"race-target-{repetition}",
            request_id=f"race-{repetition}",
            idempotency_key=f"race-{repetition}-idem",
        )
        reached, resume = Event(), Event()
        consolidator = PauseAfterRevalidateConsolidator(
            SQLiteMemoryStore(db_path), reached=reached, resume=resume
        )
        parent_id, _revision_id = parent.split("@", 1)

        def revoke_parent(memory_id=parent_id, index=repetition) -> None:
            SQLiteMemoryStore(db_path).revoke_memory(
                actor=actor,
                memory_id=memory_id,
                reason_code="I3_RACE_REVOKE",
                policy_decision_ref="policy/race-revoke",
                correlation_id=f"i3-race-revoke-{index}",
            )

        result = _run_paused(consolidator, request, revoke_parent)

        assert result.status is ConsolidationStatus.REJECTED
        assert result.rejected_reasons == ("MEMORY_NOT_EFFECTIVE",)
        assert result.candidate_revision_ref is None
        target_id = consolidator._memory_id(request)
        assert SQLiteMemoryStore(db_path).primary_content_rows(memory_id=target_id) == 0
