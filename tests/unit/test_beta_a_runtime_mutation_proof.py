from __future__ import annotations

import json

import pytest

from test_workflow.beta_runtime.artifacts import ArtifactStore
from test_workflow.beta_runtime.store import (
    JobConflictError,
    LeaseError,
    RuntimeStore,
    StaleWriteError,
)
from test_workflow.beta_runtime.verifier import VerificationInput, verify_attempt
from tests.beta_a_helpers import make_governed_fixture

NODE = "tests/test_governed.py::test_governed_unit"


def _report(store: ArtifactStore, outcome: str = "passed"):
    return store.put_text(json.dumps({"nodeid": NODE, "when": "call", "outcome": outcome}))


def _verify(
    store: ArtifactStore,
    ref,
    *,
    collected=(NODE,),
    artifact_refs=None,
    unchanged=True,
    cleanup=True,
    exit_code=0,
):
    refs = artifact_refs if artifact_refs is not None else (ref.as_dict(),)
    return verify_attempt(
        VerificationInput(
            required_node_ids=(NODE,),
            collected_node_ids=tuple(collected),
            runtime_report_path=store.resolve(ref),
            command_exit_code=exit_code,
            artifact_refs=tuple(refs),
            product_source_unchanged=unchanged,
            cleanup_verified=cleanup,
        ),
        store,
    )


def test_mutant_01_remove_submission_fingerprint_rebound_rejection_is_killed(tmp_path):
    bundle, _, manifests, submission_path = make_governed_fixture(tmp_path)
    store = RuntimeStore(tmp_path / "state")
    store.submit(bundle, now=0.0)
    (manifests / "objective.yaml").write_text(
        "objective_id: changed\nsummary: rebound\n",
        encoding="utf-8",
    )
    from test_workflow.beta_runtime.models import load_submission_bundle

    rebound = load_submission_bundle(submission_path)
    with pytest.raises(JobConflictError):
        store.submit(rebound, now=1.0)


def test_mutant_02_remove_expected_revision_or_lease_fencing_is_killed(tmp_path):
    bundle, _, _, _ = make_governed_fixture(tmp_path)
    store = RuntimeStore(tmp_path / "state")
    job, _ = store.submit(bundle, now=0.0)
    ready = store.transition(
        job.job_id,
        expected_revision=0,
        new_state="READY_TO_EXECUTE",
        event_type="READY",
        now=1.0,
    )
    with pytest.raises(StaleWriteError):
        store.transition(
            job.job_id,
            expected_revision=0,
            new_state="BLOCKED",
            event_type="STALE",
            now=2.0,
        )
    claimed = store.claim_ready(worker_id="worker", now=2.0, lease_ttl_seconds=2.0)
    assert claimed is not None and claimed[0].revision > ready.revision
    with pytest.raises(LeaseError):
        store.heartbeat(claimed[1], now=4.0)


def test_mutant_03_remove_required_node_collection_completeness_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    ref = _report(artifacts)
    result = _verify(artifacts, ref, collected=())
    assert result.verdict == "TEST_DEFECT"
    assert result.terminal_state == "FAILED"


def test_mutant_04_allow_skipped_or_deselected_required_node_success_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    skipped = _report(artifacts, "skipped")
    result = _verify(artifacts, skipped)
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.terminal_state == "BLOCKED"


def test_mutant_05_remove_evidence_completeness_before_success_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    ref = _report(artifacts)
    result = _verify(artifacts, ref, artifact_refs=())
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_mutant_06_remove_artifact_hash_verification_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    ref = _report(artifacts)
    artifacts.resolve(ref).write_text("tampered", encoding="utf-8")
    result = _verify(artifacts, ref)
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_mutant_07_remove_product_source_diff_rejection_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    ref = _report(artifacts)
    result = _verify(artifacts, ref, unchanged=False)
    assert result.verdict == "POLICY_BLOCKED"
    assert result.terminal_state == "BLOCKED"


def test_mutant_08_remove_cancellation_process_tree_proof_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    ref = _report(artifacts)
    result = _verify(artifacts, ref, cleanup=False)
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.terminal_state == "BLOCKED"


def test_mutant_09_auto_reexecute_uncertain_restart_is_killed(tmp_path):
    bundle, _, _, _ = make_governed_fixture(tmp_path)
    store = RuntimeStore(tmp_path / "state")
    job, _ = store.submit(bundle, now=0.0)
    store.transition(
        job.job_id,
        expected_revision=0,
        new_state="READY_TO_EXECUTE",
        event_type="READY",
        now=1.0,
    )
    claimed = store.claim_ready(worker_id="worker", now=2.0, lease_ttl_seconds=2.0)
    assert claimed is not None
    store.mark_command_started(claimed[1], {"argv": ["pytest"]}, now=2.5)
    outcome = store.reconcile_expired_attempts(now=4.0)
    assert outcome["blocked"] == [job.job_id]
    assert store.get_job(job.job_id).state == "BLOCKED"
    assert store.claim_ready(worker_id="second-worker", now=5.0) is None


def test_mutant_10_allow_exit_code_only_success_is_killed(tmp_path):
    artifacts = ArtifactStore(tmp_path)
    empty = artifacts.put_text("")
    result = _verify(artifacts, empty, exit_code=0)
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.terminal_state == "BLOCKED"
