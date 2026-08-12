from __future__ import annotations

import json
from pathlib import Path

from test_workflow.beta_runtime.runtime import RuntimeService
from test_workflow.beta_runtime.verifier import VerificationInput, verify_attempt
from tests.beta_a_helpers import make_governed_fixture


class _NoExecutionSandbox:
    def __getattr__(self, name: str):
        raise AssertionError(f"sandbox must not be used during durable recovery: {name}")


def _seed_crash_after_complete_evidence(tmp_path: Path):
    bundle, _, _, _ = make_governed_fixture(tmp_path)
    state = tmp_path / "state"
    service = RuntimeService(state, sandbox=_NoExecutionSandbox())
    store = service.store

    accepted, _ = store.submit(bundle, now=0.0)
    ready = store.transition(
        accepted.job_id,
        expected_revision=accepted.revision,
        new_state="READY_TO_EXECUTE",
        event_type="TEST_READY",
        now=1.0,
    )
    claimed = store.claim_ready(
        worker_id="worker-before-crash",
        now=2.0,
        lease_ttl_seconds=1000.0,
    )
    assert claimed is not None
    executing, lease = claimed
    lease = store.mark_command_started(
        lease,
        {"argv": ["pytest", "governed-pack"]},
        now=3.0,
    )

    node = "tests/test_governed.py::test_governed_unit"
    report_ref = service.artifacts.put_text(
        json.dumps({"nodeid": node, "when": "call", "outcome": "passed"}) + "\n",
        media_type="application/x-ndjson",
    )
    verification_input = VerificationInput(
        required_node_ids=(node,),
        collected_node_ids=(node,),
        runtime_report_path=service.artifacts.resolve(report_ref),
        command_exit_code=0,
        artifact_refs=(report_ref.as_dict(),),
        product_source_unchanged=True,
        cleanup_verified=True,
    )
    snapshot_ref = service._persist_verification_input(
        executing,
        lease,
        verification_input,
        report_ref,
    )
    verification = verify_attempt(verification_input, service.artifacts)
    result = verification.as_dict()
    result.update(
        {
            "attempt_id": lease.attempt_id,
            "project_source_digest_before": "stable-source",
            "project_source_digest_after": "stable-source",
            "artifacts": {"runtime_report": report_ref.as_dict()},
            "automatic_reexecution": False,
        }
    )
    evidence_manifest = {
        "schema_version": 1,
        "job_id": executing.job_id,
        "attempt_id": lease.attempt_id,
        "request_fingerprint": executing.request_fingerprint,
        "bindings": executing.submission.get("bindings", {}),
        "verdict": result["verdict"],
        "terminal_state": result["terminal_state"],
        "artifacts": result["artifacts"],
        "result": dict(result),
        "verification_input": snapshot_ref.as_dict(),
    }
    evidence_ref = service.artifacts.put_json(evidence_manifest)
    store.set_attempt_evidence(
        lease,
        {"evidence_manifest": evidence_ref.as_dict()},
        state="COMPLETED",
        now=4.0,
    )

    crashed_job = store.get_job(ready.job_id)
    assert crashed_job.state == "EXECUTING"
    assert crashed_job.result is None
    return state, crashed_job.job_id, snapshot_ref


def test_restart_reverifies_complete_evidence_without_reexecuting_docker(tmp_path):
    state, job_id, _ = _seed_crash_after_complete_evidence(tmp_path)

    restarted = RuntimeService(state, sandbox=_NoExecutionSandbox())
    assert restarted.serve_once(worker_id="worker-after-crash") == job_id

    recovered = restarted.store.get_job(job_id)
    assert recovered.state == "SUCCEEDED"
    assert recovered.result["verdict"] == "VERIFIED_SUCCESS"
    assert recovered.result["automatic_reexecution"] is False
    assert recovered.result["evidence_manifest"]["sha256"]
    assert restarted.store.next_recoverable_evidence() is None
    assert restarted.store.claim_ready(worker_id="must-not-run", now=2000.0) is None
    assert restarted.store.events(job_id)[-1]["event_type"] == (
        "VERDICT_RECOVERED_FROM_DURABLE_EVIDENCE"
    )


def test_restart_blocks_tampered_verification_snapshot_without_reexecution(tmp_path):
    state, job_id, snapshot_ref = _seed_crash_after_complete_evidence(tmp_path)
    artifact_path = RuntimeService(
        state,
        sandbox=_NoExecutionSandbox(),
    ).artifacts.resolve(snapshot_ref)
    artifact_path.write_text("tampered", encoding="utf-8")

    restarted = RuntimeService(state, sandbox=_NoExecutionSandbox())
    assert restarted.serve_once(worker_id="worker-after-tamper") == job_id

    blocked = restarted.store.get_job(job_id)
    assert blocked.state == "BLOCKED"
    assert blocked.result["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert blocked.result["automatic_reexecution"] is False
    assert "deterministically reverified" in blocked.result["reason"]
    assert restarted.store.claim_ready(worker_id="must-not-run", now=2000.0) is None
    assert restarted.store.events(job_id)[-1]["event_type"] == (
        "RECOVERY_EVIDENCE_REJECTED"
    )
