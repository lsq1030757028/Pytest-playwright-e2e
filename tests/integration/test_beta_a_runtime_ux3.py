from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


PERSONAS = (
    "first-time-engineer",
    "scripting-automation-user",
    "recovery-focused-operator",
)
REPETITIONS = 3


def _cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        [sys.executable, "-m", "test_workflow.test_agent_cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == expected_exit, (
        f"CLI exit {process.returncode}, expected {expected_exit}\n"
        f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
    )
    return process


def _json(process: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(process.stdout)


def _submit(
    root: pathlib.Path,
    *,
    persona: str,
    repetition: int,
) -> tuple[pathlib.Path, str]:
    from tests.beta_a_helpers import make_governed_fixture

    _, _, _, submission_path = make_governed_fixture(
        root,
        idempotency_key=f"ux3-{persona}-{repetition}",
    )
    state = root / "state"
    submitted = _json(
        _cli(
            "job",
            "submit",
            str(submission_path),
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert submitted["state"] == "ACCEPTED"
    assert submitted["accepted_is_success"] is False
    assert submitted["created"] is True
    return state, str(submitted["job_id"])


def _pending_result(state: pathlib.Path, job_id: str) -> dict:
    pending = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
            expected_exit=3,
        )
    )
    assert pending == {
        "job_id": job_id,
        "message": "deterministic verdict is not ready",
        "result_ready": False,
        "state": "ACCEPTED",
    }
    return pending


def _first_time_journey(root: pathlib.Path, repetition: int) -> dict:
    state, job_id = _submit(root, persona=PERSONAS[0], repetition=repetition)
    _pending_result(state, job_id)

    status = _cli("job", "status", job_id, "--state-dir", str(state))
    assert "state: ACCEPTED" in status.stdout
    assert "cancel_requested: False" in status.stdout

    events = _cli("job", "events", job_id, "--state-dir", str(state))
    assert "JOB_ACCEPTED" in events.stdout

    cancel = _cli("job", "cancel", job_id, "--state-dir", str(state))
    assert "cancellation requested; terminal CANCELLED requires cleanup proof" in cancel.stdout
    assert "state: ACCEPTED" in cancel.stdout

    processed = _cli(
        "runtime",
        "serve",
        "--once",
        "--worker-id",
        f"ux3-first-time-{repetition}",
        "--state-dir",
        str(state),
    )
    assert f"processed_job_id: {job_id}" in processed.stdout

    result = _cli("job", "result", job_id, "--state-dir", str(state))
    assert "state: CANCELLED" in result.stdout
    assert "cleanup_verified" in result.stdout
    assert "CANCELLED" in result.stdout

    restarted = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert restarted["result_ready"] is True
    assert restarted["state"] == "CANCELLED"
    assert restarted["result"]["verdict"] == "CANCELLED"
    assert restarted["result"]["cleanup_verified"] is True
    return {
        "persona": PERSONAS[0],
        "repetition": repetition,
        "accepted_is_success": False,
        "pending_verdict_visible": True,
        "cancel_request_visible": True,
        "terminal_state": "CANCELLED",
        "restart_truth_stable": True,
    }


def _automation_journey(root: pathlib.Path, repetition: int) -> dict:
    state, job_id = _submit(root, persona=PERSONAS[1], repetition=repetition)
    pending = _pending_result(state, job_id)
    assert pending["result_ready"] is False

    status = _json(
        _cli(
            "job",
            "status",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert set(status) == {
        "cancel_requested",
        "created_at",
        "job_id",
        "revision",
        "state",
        "updated_at",
    }
    assert status["state"] == "ACCEPTED"

    events = _json(
        _cli(
            "job",
            "events",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert events["events"][0]["event_type"] == "JOB_ACCEPTED"

    cancelled_request = _json(
        _cli(
            "job",
            "cancel",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert cancelled_request["cancel_requested"] is True
    assert "cleanup proof" in cancelled_request["message"]

    served = _json(
        _cli(
            "runtime",
            "serve",
            "--once",
            "--worker-id",
            f"ux3-script-{repetition}",
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert served == {"processed_job_id": job_id}

    first_result = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    second_result = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert second_result == first_result
    assert first_result["result"]["verdict"] == "CANCELLED"
    return {
        "persona": PERSONAS[1],
        "repetition": repetition,
        "json_contract_stable": True,
        "pending_exit_code": 3,
        "terminal_state": "CANCELLED",
        "restart_truth_stable": True,
    }


def _recovery_journey(root: pathlib.Path, repetition: int) -> dict:
    from test_workflow.beta_runtime.store import RuntimeStore

    state, job_id = _submit(root, persona=PERSONAS[2], repetition=repetition)
    _pending_result(state, job_id)

    store = RuntimeStore(state)
    accepted = store.get_job(job_id)
    store.transition(
        job_id,
        expected_revision=accepted.revision,
        new_state="READY_TO_EXECUTE",
        event_type="UX3_PREFLIGHT_VERIFIED",
        now=1.0,
    )
    claimed = store.claim_ready(
        worker_id=f"ux3-recovery-{repetition}",
        now=2.0,
        lease_ttl_seconds=10.0,
    )
    assert claimed is not None
    _, lease = claimed
    store.mark_command_started(
        lease,
        {"argv": ["python", "-m", "pytest"], "automatic_retry": False},
        now=3.0,
    )

    executing = _json(
        _cli(
            "job",
            "status",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert executing["state"] == "EXECUTING"
    assert executing["cancel_requested"] is False

    not_verified = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
            expected_exit=3,
        )
    )
    assert not_verified["state"] == "EXECUTING"
    assert not_verified["result_ready"] is False

    blocked = RuntimeStore(state).reconcile_expired_attempts(now=13.0)
    assert blocked == {"reclaimed": [], "blocked": [job_id]}

    interrupted_result = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert interrupted_result["state"] == "BLOCKED"
    assert interrupted_result["result"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert interrupted_result["result"]["reason"] == "ABANDONED_UNCERTAIN"
    assert interrupted_result["result"]["automatic_reexecution"] is False

    after_restart = _json(
        _cli(
            "runtime",
            "serve",
            "--once",
            "--worker-id",
            f"ux3-restarted-{repetition}",
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert after_restart == {"processed_job_id": None}
    replayed_result = _json(
        _cli(
            "job",
            "result",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert replayed_result == interrupted_result

    events = _json(
        _cli(
            "job",
            "events",
            job_id,
            "--state-dir",
            str(state),
            "--json",
        )
    )
    assert events["events"][-1]["event_type"] == "UNCERTAIN_EXECUTION_BLOCKED"
    return {
        "persona": PERSONAS[2],
        "repetition": repetition,
        "executing_not_verified": True,
        "adversarial_environment": "worker-interruption-after-command-start",
        "terminal_state": "BLOCKED",
        "reason": "ABANDONED_UNCERTAIN",
        "automatic_reexecution": False,
        "restart_truth_stable": True,
    }


def _prove_failure_taxonomy(root: pathlib.Path) -> list[dict]:
    from test_workflow.beta_runtime.artifacts import ArtifactStore
    from test_workflow.beta_runtime.store import RuntimeStore

    visible: list[dict] = []
    for index, verdict in enumerate(
        ("PRODUCT_DEFECT", "TEST_DEFECT", "ENVIRONMENT_FAILURE"),
        start=1,
    ):
        case_root = root / verdict.lower()
        state, job_id = _submit(
            case_root,
            persona=f"taxonomy-{verdict.lower()}",
            repetition=index,
        )
        store = RuntimeStore(state)
        accepted = store.get_job(job_id)
        store.transition(
            job_id,
            expected_revision=accepted.revision,
            new_state="READY_TO_EXECUTE",
            event_type="UX3_TAXONOMY_READY",
            now=1.0,
        )
        claimed = store.claim_ready(
            worker_id=f"ux3-taxonomy-{index}",
            now=2.0,
            lease_ttl_seconds=10.0,
        )
        assert claimed is not None
        executing, lease = claimed
        lease = store.mark_command_started(
            lease,
            {"argv": ["python", "-m", "pytest"], "automatic_retry": False},
            now=3.0,
        )
        artifact = ArtifactStore(state / "artifacts").put_text(
            f"UX3 durable evidence for {verdict}\n"
        )
        evidence_manifest = {
            "attempt_id": lease.attempt_id,
            "artifacts": {"summary": artifact.as_dict()},
        }
        store.set_attempt_evidence(lease, evidence_manifest, state="FAILED", now=4.0)
        result = {
            "verdict": verdict,
            "terminal_state": "FAILED",
            "reason": f"UX3 controlled {verdict} visibility fixture",
            "cleanup_verified": True,
            "automatic_reexecution": False,
            "artifacts": {"summary": artifact.as_dict()},
        }
        store.transition(
            job_id,
            expected_revision=executing.revision,
            new_state="FAILED",
            event_type="UX3_TAXONOMY_FINALIZED",
            payload={"verdict": verdict},
            result=result,
            lease_token=lease.lease_token,
            now=5.0,
        )

        rendered = _json(
            _cli(
                "job",
                "result",
                job_id,
                "--state-dir",
                str(state),
                "--json",
            )
        )
        assert rendered["state"] == "FAILED"
        assert rendered["result"]["verdict"] == verdict
        assert rendered["result"]["artifacts"]["summary"]["sha256"] == artifact.sha256
        visible.append(
            {
                "verdict": verdict,
                "terminal_state": rendered["state"],
                "evidence_reference_visible": True,
            }
        )
    return visible


def test_beta_a_ux3_real_cli_persona_matrix(tmp_path):
    journeys: list[dict] = []
    for repetition in range(1, REPETITIONS + 1):
        journeys.append(_first_time_journey(tmp_path / f"first-time-{repetition}", repetition))
        journeys.append(_automation_journey(tmp_path / f"automation-{repetition}", repetition))
        journeys.append(_recovery_journey(tmp_path / f"recovery-{repetition}", repetition))

    assert len(journeys) == len(PERSONAS) * REPETITIONS
    for persona in PERSONAS:
        assert sum(item["persona"] == persona for item in journeys) == REPETITIONS

    taxonomy = _prove_failure_taxonomy(tmp_path / "taxonomy")
    assert [item["verdict"] for item in taxonomy] == [
        "PRODUCT_DEFECT",
        "TEST_DEFECT",
        "ENVIRONMENT_FAILURE",
    ]

    report = {
        "schema_version": "1.0",
        "assurance": "UX3",
        "real_cli_process_invocation": True,
        "durable_state_backend": "SQLite",
        "personas": list(PERSONAS),
        "repetitions_per_persona": REPETITIONS,
        "journey_count": len(journeys),
        "journeys": journeys,
        "failure_taxonomy": taxonomy,
        "adversarial_recovery": {
            "covered": True,
            "failure_point": "after-command-start-before-trusted-evidence",
            "expected_truth": "BLOCKED/ABANDONED_UNCERTAIN",
            "automatic_reexecution": False,
        },
        "ux_assertions": {
            "accepted_is_not_success": True,
            "executing_is_not_verified": True,
            "blocked_explains_missing_trusted_verdict": True,
            "failure_classes_are_distinguishable": True,
            "cancellation_request_and_terminal_state_are_distinguishable": True,
            "evidence_references_are_discoverable": True,
            "restart_uncertainty_is_visible": True,
        },
    }

    report_path = os.environ.get("BETA_A_UX3_REPORT")
    if report_path:
        destination = pathlib.Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
