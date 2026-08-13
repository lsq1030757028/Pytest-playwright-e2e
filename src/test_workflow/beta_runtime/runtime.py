from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .artifacts import ArtifactRef, ArtifactStore
from .models import SubmissionBundle
from .sandbox import (
    DockerSandbox,
    SandboxPolicyError,
    SandboxUnavailable,
    source_tree_digest,
    validate_project_tree,
)
from .store import AttemptLease, JobRecord, RuntimeStore
from .verifier import VerificationInput, verify_attempt


class RuntimeValidationError(RuntimeError):
    pass


def _minimal_git_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1"}


def _git(project: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        env=_minimal_git_env(),
        timeout=20,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeValidationError(
            process.stderr.strip() or "git verification failed"
        )
    return process.stdout.strip()


def _ref_dict(ref: ArtifactRef) -> dict[str, Any]:
    return ref.as_dict()


class RuntimeService:
    def __init__(
        self,
        state_dir: Path,
        *,
        sandbox: DockerSandbox | None = None,
    ) -> None:
        self.state_dir = state_dir.resolve()
        self.store = RuntimeStore(self.state_dir)
        self.artifacts = ArtifactStore(self.state_dir / "artifacts")
        self.sandbox = sandbox or DockerSandbox()
        self.work_root = self.state_dir / "work"
        self.work_root.mkdir(parents=True, exist_ok=True)

    def submit(self, bundle: SubmissionBundle) -> tuple[JobRecord, bool]:
        self._verify_project_identity(
            bundle.project_profile.checkout_path,
            bundle.submission,
        )
        validate_project_tree(bundle.project_profile.checkout_path)
        return self.store.submit(bundle)

    def serve_once(self, *, worker_id: str = "worker-1") -> str | None:
        recovered_job_id = self._recover_durable_evidence()
        if recovered_job_id is not None:
            return recovered_job_id

        self.store.reconcile_expired_attempts(now=time.time())
        processed_job_id: str | None = None

        accepted = self.store.next_job("ACCEPTED")
        if accepted is not None:
            processed_job_id = accepted.job_id
            self._prepare_job(accepted)

        claimed = self.store.claim_ready(worker_id=worker_id, now=time.time())
        if claimed is None:
            return processed_job_id
        job, lease = claimed
        self._execute(job, lease)
        return job.job_id

    def _prepare_job(self, job: JobRecord) -> None:
        if job.cancel_requested:
            self.store.transition(
                job.job_id,
                expected_revision=job.revision,
                new_state="CANCELLED",
                event_type="JOB_CANCELLED_BEFORE_EXECUTION",
                result={
                    "verdict": "CANCELLED",
                    "terminal_state": "CANCELLED",
                    "reason": "cancelled before governed execution began",
                    "cleanup_verified": True,
                },
            )
            return

        payload = job.submission
        project_path = Path(payload["resolved"]["checkout_path"])
        image = str(payload["resolved"]["execution_image"])
        try:
            self._verify_project_identity(project_path, payload["submission"])
            validate_project_tree(project_path)
            self.sandbox.ensure_available(image)
        except SandboxPolicyError as exc:
            self._finish_preflight_failure(
                job,
                verdict="POLICY_BLOCKED",
                terminal_state="BLOCKED",
                reason=str(exc),
            )
            return
        except SandboxUnavailable as exc:
            self._finish_preflight_failure(
                job,
                verdict="ENVIRONMENT_FAILURE",
                terminal_state="FAILED",
                reason=str(exc),
            )
            return

        before_digest = source_tree_digest(project_path)
        self.store.transition(
            job.job_id,
            expected_revision=job.revision,
            new_state="READY_TO_EXECUTE",
            event_type="PREFLIGHT_VERIFIED",
            payload={"project_source_digest": before_digest},
        )

    def _finish_preflight_failure(
        self,
        job: JobRecord,
        *,
        verdict: str,
        terminal_state: str,
        reason: str,
    ) -> None:
        result = {
            "verdict": verdict,
            "terminal_state": terminal_state,
            "reason": reason,
            "attempt_started": False,
            "automatic_reexecution": False,
        }
        self.store.transition(
            job.job_id,
            expected_revision=job.revision,
            new_state=terminal_state,
            event_type="PREFLIGHT_FAILED",
            payload={"verdict": verdict, "reason": reason},
            result=result,
        )

    @staticmethod
    def _verify_project_identity(
        project_path: Path,
        submission: dict[str, Any],
    ) -> None:
        expected_commit = str(submission["commit_sha"])
        expected_repository = str(submission["project_repository"])
        head = _git(project_path, "rev-parse", "HEAD")
        if head != expected_commit:
            raise RuntimeValidationError(
                "project checkout HEAD does not match pinned commit"
            )
        remote = _git(project_path, "remote", "get-url", "origin")
        if remote != expected_repository:
            raise RuntimeValidationError(
                "project checkout origin does not match submission repository"
            )

    def _execute(self, job: JobRecord, lease: AttemptLease) -> None:
        payload = job.submission
        project_path = Path(payload["resolved"]["checkout_path"])
        image = str(payload["resolved"]["execution_image"])
        selected = tuple(
            str(value) for value in payload["resolved"]["selected_node_ids"]
        )
        required = tuple(
            str(value) for value in payload["resolved"]["required_node_ids"]
        )
        scratch = (self.work_root / lease.attempt_id).resolve()
        scratch.mkdir(parents=True, exist_ok=True)

        try:
            self.sandbox.ensure_available(image)
            validate_project_tree(project_path)
        except SandboxPolicyError as exc:
            self._finish_prelaunch_attempt(
                job,
                lease,
                verdict="POLICY_BLOCKED",
                terminal_state="BLOCKED",
                reason=str(exc),
            )
            return
        except SandboxUnavailable as exc:
            self._finish_prelaunch_attempt(
                job,
                lease,
                verdict="ENVIRONMENT_FAILURE",
                terminal_state="FAILED",
                reason=str(exc),
            )
            return

        before_digest = source_tree_digest(project_path)
        command_manifest = self.sandbox.command_manifest(
            image=image,
            project_path=project_path,
            selected_node_ids=selected,
            attempt_id=lease.attempt_id,
        )
        command_ref = self.artifacts.put_json(command_manifest)
        command_manifest["artifact"] = _ref_dict(command_ref)
        lease = self.store.mark_command_started(
            lease,
            command_manifest,
            now=time.time(),
        )
        current_lease = lease

        def heartbeat(now: float) -> None:
            nonlocal current_lease
            current_lease = self.store.heartbeat(current_lease, now=now)

        run = self.sandbox.run(
            image=image,
            project_path=project_path,
            scratch_path=scratch,
            selected_node_ids=selected,
            attempt_id=lease.attempt_id,
            timeout_seconds=self._attempt_timeout_seconds(payload),
            cancel_requested=lambda: self.store.is_cancel_requested(job.job_id),
            heartbeat=heartbeat,
        )
        lease = current_lease
        after_digest = source_tree_digest(project_path)

        named_artifacts = self._capture_attempt_artifacts(
            scratch,
            docker_stdout=run.stdout,
            docker_stderr=run.stderr,
        )
        named_artifacts["command_manifest"] = command_ref
        artifact_index = {
            name: _ref_dict(ref)
            for name, ref in sorted(named_artifacts.items())
        }

        if run.cancelled:
            if run.cleanup_verified:
                result = {
                    "verdict": "CANCELLED",
                    "terminal_state": "CANCELLED",
                    "reason": (
                        "durable cancellation observed and Docker process tree removed"
                    ),
                    "cleanup_verified": True,
                    "artifacts": artifact_index,
                }
                self._finish(job.job_id, lease, result, attempt_state="CANCELLED")
            else:
                result = {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "terminal_state": "BLOCKED",
                    "reason": (
                        "cancellation requested but process cleanup could not be verified"
                    ),
                    "cleanup_verified": False,
                    "artifacts": artifact_index,
                }
                self._finish(job.job_id, lease, result, attempt_state="FAILED")
            return

        if run.timed_out:
            result = {
                "verdict": "TIMED_OUT",
                "terminal_state": "TIMED_OUT",
                "reason": "bounded execution attempt exceeded time budget",
                "cleanup_verified": run.cleanup_verified,
                "artifacts": artifact_index,
            }
            self._finish(job.job_id, lease, result, attempt_state="TIMED_OUT")
            return

        meta_ref = named_artifacts.get("entry_meta")
        collection_ref = named_artifacts.get("collection")
        runtime_report_ref = named_artifacts.get("runtime_report")
        meta = self._load_json_artifact(meta_ref)
        collection = self._load_json_artifact(collection_ref)
        collected = tuple(str(value) for value in collection.get("node_ids", []))
        execution_code_raw = meta.get("execution_exit_code")
        execution_code = (
            int(execution_code_raw)
            if execution_code_raw is not None
            else int(run.exit_code)
        )
        infrastructure_error = None
        if int(run.exit_code) == 125:
            infrastructure_error = (
                "Docker runtime rejected or failed to start governed execution"
            )

        runtime_report_path = (
            self.artifacts.resolve(runtime_report_ref)
            if runtime_report_ref is not None
            else scratch / "missing-runtime-report.jsonl"
        )
        verification_input = VerificationInput(
            required_node_ids=required,
            collected_node_ids=collected,
            runtime_report_path=runtime_report_path,
            command_exit_code=execution_code,
            artifact_refs=tuple(
                _ref_dict(ref) for ref in named_artifacts.values()
            ),
            product_source_unchanged=before_digest == after_digest,
            cleanup_verified=run.cleanup_verified,
            infrastructure_error=infrastructure_error,
        )
        verification_input_ref = self._persist_verification_input(
            job,
            lease,
            verification_input,
            runtime_report_ref,
        )
        verification = verify_attempt(verification_input, self.artifacts)
        result = verification.as_dict()
        result.update(
            {
                "attempt_id": lease.attempt_id,
                "project_source_digest_before": before_digest,
                "project_source_digest_after": after_digest,
                "artifacts": artifact_index,
                "automatic_reexecution": False,
            }
        )
        attempt_state = (
            "COMPLETED"
            if verification.terminal_state == "SUCCEEDED"
            else "FAILED"
        )
        self._finish(
            job.job_id,
            lease,
            result,
            attempt_state=attempt_state,
            verification_input_ref=verification_input_ref,
        )

    def _finish_prelaunch_attempt(
        self,
        job: JobRecord,
        lease: AttemptLease,
        *,
        verdict: str,
        terminal_state: str,
        reason: str,
    ) -> None:
        result = {
            "verdict": verdict,
            "terminal_state": terminal_state,
            "reason": reason,
            "attempt_id": lease.attempt_id,
            "command_started": False,
            "automatic_reexecution": False,
        }
        now = time.time()
        self.store.set_attempt_evidence(
            lease,
            {"prelaunch_result": result},
            state="FAILED",
            now=now,
        )
        current = self.store.get_job(job.job_id)
        self.store.transition(
            job.job_id,
            expected_revision=current.revision,
            new_state=terminal_state,
            event_type="PRELAUNCH_ATTEMPT_FAILED",
            payload={"verdict": verdict, "reason": reason},
            result=result,
            lease_token=lease.lease_token,
            now=now,
        )

    def _finish(
        self,
        job_id: str,
        lease: AttemptLease,
        result: dict[str, Any],
        *,
        attempt_state: str,
        verification_input_ref: ArtifactRef | None = None,
    ) -> None:
        current_job = self.store.get_job(job_id)
        intended_result = dict(result)
        evidence_manifest = {
            "schema_version": 1,
            "job_id": job_id,
            "attempt_id": lease.attempt_id,
            "request_fingerprint": current_job.request_fingerprint,
            "bindings": current_job.submission.get("bindings", {}),
            "verdict": result["verdict"],
            "terminal_state": result["terminal_state"],
            "artifacts": result.get("artifacts", {}),
            "result": intended_result,
        }
        if verification_input_ref is not None:
            evidence_manifest["verification_input"] = _ref_dict(
                verification_input_ref
            )
        evidence_ref = self.artifacts.put_json(evidence_manifest)
        result["evidence_manifest"] = _ref_dict(evidence_ref)
        now = time.time()
        self.store.set_attempt_evidence(
            lease,
            {"evidence_manifest": _ref_dict(evidence_ref)},
            state=attempt_state,
            now=now,
        )
        current = self.store.get_job(job_id)
        self.store.transition(
            job_id,
            expected_revision=current.revision,
            new_state=str(result["terminal_state"]),
            event_type="VERDICT_FINALIZED",
            payload={
                "verdict": result["verdict"],
                "attempt_id": lease.attempt_id,
            },
            result=result,
            lease_token=lease.lease_token,
            now=now,
        )

    def _persist_verification_input(
        self,
        job: JobRecord,
        lease: AttemptLease,
        value: VerificationInput,
        runtime_report_ref: ArtifactRef | None,
    ) -> ArtifactRef:
        snapshot = {
            "schema_version": 1,
            "job_id": job.job_id,
            "attempt_id": lease.attempt_id,
            "request_fingerprint": job.request_fingerprint,
            "bindings": job.submission.get("bindings", {}),
            "required_node_ids": list(value.required_node_ids),
            "collected_node_ids": list(value.collected_node_ids),
            "runtime_report": (
                _ref_dict(runtime_report_ref)
                if runtime_report_ref is not None
                else None
            ),
            "command_exit_code": value.command_exit_code,
            "artifact_refs": list(value.artifact_refs),
            "product_source_unchanged": value.product_source_unchanged,
            "cleanup_verified": value.cleanup_verified,
            "policy_conflict": value.policy_conflict,
            "oracle_conflict": value.oracle_conflict,
            "infrastructure_error": value.infrastructure_error,
        }
        return self.artifacts.put_json(snapshot)

    def _recover_durable_evidence(self) -> str | None:
        candidate = self.store.next_recoverable_evidence()
        if candidate is None:
            return None
        job, attempt = candidate
        attempt_id = str(attempt["attempt_id"])
        now = time.time()
        try:
            wrapper = attempt["evidence_manifest"]
            if not isinstance(wrapper, dict):
                raise RuntimeValidationError("recovery evidence wrapper is invalid")
            evidence_ref = wrapper.get("evidence_manifest")
            evidence = self._load_recovery_json_ref(
                evidence_ref,
                label="evidence manifest",
            )
            self._assert_recovery_binding(evidence, job, attempt_id)

            snapshot_ref = evidence.get("verification_input")
            snapshot = self._load_recovery_json_ref(
                snapshot_ref,
                label="verification input",
            )
            self._assert_recovery_binding(snapshot, job, attempt_id)
            verification_input = self._verification_from_snapshot(snapshot)
            verification = verify_attempt(verification_input, self.artifacts)

            intended_result = evidence.get("result")
            if not isinstance(intended_result, dict):
                raise RuntimeValidationError("durable intended result is missing")
            expected = verification.as_dict()
            for key, expected_value in expected.items():
                if intended_result.get(key) != expected_value:
                    raise RuntimeValidationError(
                        "reverified verdict does not match durable intended result"
                    )
            if evidence.get("verdict") != expected["verdict"]:
                raise RuntimeValidationError("evidence verdict binding changed")
            if evidence.get("terminal_state") != expected["terminal_state"]:
                raise RuntimeValidationError("evidence terminal-state binding changed")
            if evidence.get("artifacts") != intended_result.get("artifacts", {}):
                raise RuntimeValidationError("evidence artifact index binding changed")

            result = dict(intended_result)
            if not isinstance(evidence_ref, dict):
                raise RuntimeValidationError("evidence reference is invalid")
            result["evidence_manifest"] = dict(evidence_ref)
            self.store.finalize_recovered_evidence(
                job.job_id,
                attempt_id=attempt_id,
                expected_revision=job.revision,
                result=result,
                event_type="VERDICT_RECOVERED_FROM_DURABLE_EVIDENCE",
                now=now,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            result = {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "terminal_state": "BLOCKED",
                "reason": (
                    "durable post-execution evidence could not be deterministically "
                    f"reverified after restart: {exc}"
                ),
                "attempt_id": attempt_id,
                "automatic_reexecution": False,
            }
            self.store.finalize_recovered_evidence(
                job.job_id,
                attempt_id=attempt_id,
                expected_revision=job.revision,
                result=result,
                event_type="RECOVERY_EVIDENCE_REJECTED",
                now=now,
            )
        return job.job_id

    def _load_recovery_json_ref(
        self,
        ref: Any,
        *,
        label: str,
    ) -> dict[str, Any]:
        if not isinstance(ref, dict) or not self.artifacts.verify(ref):
            raise RuntimeValidationError(f"{label} is missing or failed hash verification")
        value = json.loads(
            self.artifacts.resolve(ref).read_text(encoding="utf-8")
        )
        if not isinstance(value, dict):
            raise RuntimeValidationError(f"{label} is not a JSON object")
        return value

    @staticmethod
    def _assert_recovery_binding(
        value: dict[str, Any],
        job: JobRecord,
        attempt_id: str,
    ) -> None:
        if value.get("schema_version") != 1:
            raise RuntimeValidationError("recovery evidence schema is unsupported")
        if value.get("job_id") != job.job_id:
            raise RuntimeValidationError("recovery evidence is bound to another job")
        if value.get("attempt_id") != attempt_id:
            raise RuntimeValidationError("recovery evidence is bound to another attempt")
        if value.get("request_fingerprint") != job.request_fingerprint:
            raise RuntimeValidationError("recovery request fingerprint binding changed")
        if value.get("bindings") != job.submission.get("bindings", {}):
            raise RuntimeValidationError("recovery governed bindings changed")

    def _verification_from_snapshot(
        self,
        snapshot: dict[str, Any],
    ) -> VerificationInput:
        required = snapshot.get("required_node_ids")
        collected = snapshot.get("collected_node_ids")
        artifact_refs = snapshot.get("artifact_refs")
        report_ref = snapshot.get("runtime_report")
        exit_code = snapshot.get("command_exit_code")
        source_unchanged = snapshot.get("product_source_unchanged")
        cleanup_verified = snapshot.get("cleanup_verified")

        if not isinstance(required, list) or not all(
            isinstance(value, str) for value in required
        ):
            raise RuntimeValidationError("recovery required-node snapshot is invalid")
        if not isinstance(collected, list) or not all(
            isinstance(value, str) for value in collected
        ):
            raise RuntimeValidationError("recovery collection snapshot is invalid")
        if not isinstance(artifact_refs, list) or not all(
            isinstance(value, dict) for value in artifact_refs
        ):
            raise RuntimeValidationError("recovery artifact snapshot is invalid")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise RuntimeValidationError("recovery exit-code snapshot is invalid")
        if not isinstance(source_unchanged, bool):
            raise RuntimeValidationError("recovery source-integrity snapshot is invalid")
        if not isinstance(cleanup_verified, bool):
            raise RuntimeValidationError("recovery cleanup snapshot is invalid")

        if report_ref is None:
            report_path = self.state_dir / "missing-recovery-runtime-report.jsonl"
        else:
            if not isinstance(report_ref, dict):
                raise RuntimeValidationError("recovery runtime-report ref is invalid")
            if report_ref not in artifact_refs:
                raise RuntimeValidationError(
                    "recovery runtime-report ref is not bound to artifact set"
                )
            report_path = self.artifacts.resolve(report_ref)

        optional_text: dict[str, str | None] = {}
        for key in ("policy_conflict", "oracle_conflict", "infrastructure_error"):
            value = snapshot.get(key)
            if value is not None and not isinstance(value, str):
                raise RuntimeValidationError(f"recovery {key} snapshot is invalid")
            optional_text[key] = value

        return VerificationInput(
            required_node_ids=tuple(required),
            collected_node_ids=tuple(collected),
            runtime_report_path=report_path,
            command_exit_code=exit_code,
            artifact_refs=tuple(dict(value) for value in artifact_refs),
            product_source_unchanged=source_unchanged,
            cleanup_verified=cleanup_verified,
            policy_conflict=optional_text["policy_conflict"],
            oracle_conflict=optional_text["oracle_conflict"],
            infrastructure_error=optional_text["infrastructure_error"],
        )

    def _capture_attempt_artifacts(
        self,
        scratch: Path,
        *,
        docker_stdout: str,
        docker_stderr: str,
    ) -> dict[str, ArtifactRef]:
        refs = {
            "docker_stdout": self.artifacts.put_text(docker_stdout),
            "docker_stderr": self.artifacts.put_text(docker_stderr),
        }
        text_files = {
            "collection_stdout": "collection.stdout.txt",
            "collection_stderr": "collection.stderr.txt",
            "execution_stdout": "execution.stdout.txt",
            "execution_stderr": "execution.stderr.txt",
        }
        for key, name in text_files.items():
            path = scratch / name
            if path.is_file():
                refs[key] = self.artifacts.put_text(
                    path.read_text(encoding="utf-8", errors="replace")
                )

        typed_files = {
            "collection": ("collection.json", "application/json"),
            "entry_meta": ("entry-meta.json", "application/json"),
            "runtime_report": (
                "runtime-report.jsonl",
                "application/x-ndjson",
            ),
            "junit": ("junit.xml", "application/xml"),
        }
        for key, (name, media_type) in typed_files.items():
            path = scratch / name
            if path.is_file():
                refs[key] = self.artifacts.put_file(
                    path,
                    media_type=media_type,
                )
        return refs

    def _load_json_artifact(
        self,
        ref: ArtifactRef | None,
    ) -> dict[str, Any]:
        if ref is None or not self.artifacts.verify(ref):
            return {}
        try:
            value = json.loads(
                self.artifacts.resolve(ref).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _attempt_timeout_seconds(payload: dict[str, Any]) -> float:
        manifests = payload.get("resolved", {}).get("manifests", {})
        budget = manifests.get("budget", {}) if isinstance(manifests, dict) else {}
        requested = budget.get("execution_attempt_minutes", 15)
        if not isinstance(requested, int) or requested <= 0 or requested > 15:
            raise RuntimeValidationError("invalid durable execution attempt budget")
        return float(requested * 60)
