from __future__ import annotations

import json

import pytest
import yaml
from typer.testing import CliRunner

from test_workflow.beta_runtime.artifacts import ArtifactStore
from test_workflow.beta_runtime.models import ManifestError, load_submission_bundle
from test_workflow.beta_runtime.runtime import RuntimeService
from test_workflow.beta_runtime.store import (
    JobConflictError,
    LeaseError,
    RuntimeStore,
    StaleWriteError,
)
from test_workflow.beta_runtime.verifier import VerificationInput, verify_attempt
from test_workflow.test_agent_cli import app
from tests.beta_a_helpers import make_governed_fixture, write_yaml


def _ready(store: RuntimeStore, job_id: str, revision: int = 0, now: float = 1.0):
    return store.transition(
        job_id,
        expected_revision=revision,
        new_state="READY_TO_EXECUTE",
        event_type="TEST_READY",
        now=now,
    )


def test_submission_rejects_manifest_escape_nonhex_commit_and_floating_image(tmp_path):
    _, _, manifests, submission_path = make_governed_fixture(tmp_path)
    submission = yaml.safe_load(submission_path.read_text(encoding="utf-8"))

    outside = tmp_path / "outside.yaml"
    write_yaml(outside, {"profile_id": "escaped"})
    submission["objective_manifest_ref"] = "../outside.yaml"
    write_yaml(submission_path, submission)
    with pytest.raises(ManifestError, match="escapes"):
        load_submission_bundle(submission_path)

    _, _, manifests, submission_path = make_governed_fixture(tmp_path / "nonhex")
    submission = yaml.safe_load(submission_path.read_text(encoding="utf-8"))
    submission["commit_sha"] = "z" * 40
    write_yaml(submission_path, submission)
    with pytest.raises(ManifestError, match="hexadecimal"):
        load_submission_bundle(submission_path)

    _, _, manifests, submission_path = make_governed_fixture(tmp_path / "latest")
    environment_path = manifests / "environment.yaml"
    environment = yaml.safe_load(environment_path.read_text(encoding="utf-8"))
    environment["image"] = "beta-a-runtime-ci:latest"
    write_yaml(environment_path, environment)
    with pytest.raises(ManifestError, match="floating"):
        load_submission_bundle(submission_path)


def test_submission_requires_current_authoritative_oracle_binding(tmp_path):
    _, _, manifests, submission_path = make_governed_fixture(tmp_path)
    oracle_path = manifests / "oracle.yaml"
    oracle = yaml.safe_load(oracle_path.read_text(encoding="utf-8"))
    oracle["status"] = "STALE"
    write_yaml(oracle_path, oracle)
    with pytest.raises(ManifestError, match="not ACTIVE"):
        load_submission_bundle(submission_path)

    oracle["status"] = "ACTIVE"
    oracle["authority"] = "CANDIDATE"
    write_yaml(oracle_path, oracle)
    with pytest.raises(ManifestError, match="not AUTHORITATIVE"):
        load_submission_bundle(submission_path)


def test_idempotency_rebound_and_sqlite_restart_are_durable(tmp_path):
    bundle, _, manifests, submission_path = make_governed_fixture(tmp_path)
    state = tmp_path / "state"
    store = RuntimeStore(state)

    first, created = store.submit(bundle, now=1.0)
    second, created_again = store.submit(bundle, now=2.0)
    assert created is True
    assert created_again is False
    assert second.job_id == first.job_id

    objective_path = manifests / "objective.yaml"
    objective = yaml.safe_load(objective_path.read_text(encoding="utf-8"))
    objective["summary"] = "Changed objective must change the request fingerprint."
    write_yaml(objective_path, objective)
    rebound = load_submission_bundle(submission_path)
    with pytest.raises(JobConflictError, match="different request"):
        store.submit(rebound, now=3.0)

    restarted = RuntimeStore(state)
    persisted = restarted.get_job(first.job_id)
    assert persisted.request_fingerprint == bundle.fingerprint
    assert [event["seq"] for event in restarted.events(first.job_id)] == [1]


def test_revision_and_worker_lease_fencing_fail_closed(tmp_path):
    bundle, _, _, _ = make_governed_fixture(tmp_path)
    store = RuntimeStore(tmp_path / "state")
    job, _ = store.submit(bundle, now=0.0)
    ready = _ready(store, job.job_id)

    with pytest.raises(StaleWriteError, match="revision"):
        store.transition(
            job.job_id,
            expected_revision=job.revision,
            new_state="BLOCKED",
            event_type="STALE_WRITER",
            now=2.0,
        )

    claimed = store.claim_ready(worker_id="worker-a", now=2.0, lease_ttl_seconds=10.0)
    assert claimed is not None
    _, lease = claimed
    with pytest.raises(LeaseError, match="expired"):
        store.heartbeat(lease, now=12.0)

    assert store.get_job(job.job_id).revision > ready.revision


def test_prelaunch_lease_reclaims_but_started_attempt_never_reexecutes(tmp_path):
    bundle, _, _, _ = make_governed_fixture(tmp_path)
    state = tmp_path / "state"
    store = RuntimeStore(state)

    first, _ = store.submit(bundle, now=0.0)
    _ready(store, first.job_id)
    claimed = store.claim_ready(worker_id="worker-a", now=2.0, lease_ttl_seconds=10.0)
    assert claimed is not None
    _, lease = claimed
    reclaimed = store.reconcile_expired_attempts(now=12.0)
    assert reclaimed == {"reclaimed": [first.job_id], "blocked": []}
    assert store.get_job(first.job_id).state == "READY_TO_EXECUTE"
    reclaimed_claim = store.claim_ready(worker_id="worker-b", now=13.0)
    assert reclaimed_claim is not None
    assert reclaimed_claim[1].attempt_id == lease.attempt_id
    assert reclaimed_claim[1].lease_token != lease.lease_token

    bundle2, _, _, _ = make_governed_fixture(tmp_path / "uncertain")
    bundle2.submission["idempotency_key"] = "uncertain-key"
    second, _ = store.submit(bundle2, now=20.0)
    _ready(store, second.job_id, now=21.0)
    claimed2 = store.claim_ready(worker_id="worker-a", now=22.0, lease_ttl_seconds=10.0)
    assert claimed2 is not None
    _, lease2 = claimed2
    store.mark_command_started(lease2, {"argv": ["pytest"]}, now=23.0)
    blocked = store.reconcile_expired_attempts(now=32.0)
    assert blocked == {"reclaimed": [], "blocked": [second.job_id]}
    terminal = store.get_job(second.job_id)
    assert terminal.state == "BLOCKED"
    assert terminal.result["reason"] == "ABANDONED_UNCERTAIN"
    assert terminal.result["automatic_reexecution"] is False
    assert store.attempt_for_job(second.job_id)["state"] == "ABANDONED_UNCERTAIN"
    assert store.claim_ready(worker_id="worker-c", now=40.0) is None


def _verify(
    artifact_store: ArtifactStore,
    report_ref,
    *,
    collected=("tests/test_governed.py::test_governed_unit",),
    product_source_unchanged=True,
    cleanup_verified=True,
    command_exit_code=0,
):
    node = "tests/test_governed.py::test_governed_unit"
    return verify_attempt(
        VerificationInput(
            required_node_ids=(node,),
            collected_node_ids=tuple(collected),
            runtime_report_path=artifact_store.resolve(report_ref),
            command_exit_code=command_exit_code,
            artifact_refs=(report_ref.as_dict(),),
            product_source_unchanged=product_source_unchanged,
            cleanup_verified=cleanup_verified,
        ),
        artifact_store,
    )


def test_verifier_blocks_false_green_tamper_skip_missing_collection_and_source_diff(tmp_path):
    artifacts = ArtifactStore(tmp_path / "artifacts")
    node = "tests/test_governed.py::test_governed_unit"
    passed = artifacts.put_text(json.dumps({"nodeid": node, "when": "call", "outcome": "passed"}))
    assert _verify(artifacts, passed).verdict == "VERIFIED_SUCCESS"

    artifacts.resolve(passed).write_text("tampered", encoding="utf-8")
    tampered = _verify(artifacts, passed)
    assert tampered.verdict == "INSUFFICIENT_EVIDENCE"
    assert tampered.terminal_state == "BLOCKED"

    skipped = artifacts.put_text(json.dumps({"nodeid": node, "when": "call", "outcome": "skipped"}))
    assert _verify(artifacts, skipped).verdict == "INSUFFICIENT_EVIDENCE"
    assert _verify(artifacts, skipped, collected=()).verdict == "TEST_DEFECT"

    passed2 = artifacts.put_text(json.dumps({"nodeid": node, "when": "call", "outcome": "passed"}) + "\n")
    assert _verify(artifacts, passed2, product_source_unchanged=False).verdict == "POLICY_BLOCKED"
    assert _verify(artifacts, passed2, cleanup_verified=False).verdict == "INSUFFICIENT_EVIDENCE"

    empty = artifacts.put_text("")
    exit_zero_only = _verify(artifacts, empty, command_exit_code=0)
    assert exit_zero_only.verdict == "INSUFFICIENT_EVIDENCE"
    assert exit_zero_only.terminal_state == "BLOCKED"


def test_artifact_store_redacts_and_detects_content_substitution(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    ref = store.put_text("Authorization: Bearer super-secret\napi_key=abc123")
    materialized = store.resolve(ref).read_text(encoding="utf-8")
    assert "super-secret" not in materialized
    assert "abc123" not in materialized
    assert materialized.count("[REDACTED]") == 2
    assert store.verify(ref) is True
    store.resolve(ref).write_text("substituted", encoding="utf-8")
    assert store.verify(ref) is False


def test_cli_distinguishes_accepted_pending_cancelled_and_restart_truth(tmp_path):
    _, _, _, submission_path = make_governed_fixture(tmp_path)
    state = tmp_path / "state"
    runner = CliRunner()

    submit = runner.invoke(
        app,
        ["job", "submit", str(submission_path), "--state-dir", str(state), "--json"],
    )
    assert submit.exit_code == 0, submit.output
    accepted = json.loads(submit.stdout)
    assert accepted["state"] == "ACCEPTED"
    assert accepted["accepted_is_success"] is False
    job_id = accepted["job_id"]

    pending = runner.invoke(
        app,
        ["job", "result", job_id, "--state-dir", str(state), "--json"],
    )
    assert pending.exit_code == 3
    assert json.loads(pending.stdout)["result_ready"] is False

    cancel = runner.invoke(
        app,
        ["job", "cancel", job_id, "--state-dir", str(state), "--json"],
    )
    assert cancel.exit_code == 0
    assert json.loads(cancel.stdout)["cancel_requested"] is True

    RuntimeService(state).serve_once()
    restarted = RuntimeStore(state).get_job(job_id)
    assert restarted.state == "CANCELLED"
    assert restarted.result["verdict"] == "CANCELLED"

    result = runner.invoke(
        app,
        ["job", "result", job_id, "--state-dir", str(state), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["result_ready"] is True
    assert payload["result"]["verdict"] == "CANCELLED"
