from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .artifacts import ArtifactRef, ArtifactStore
from .models import SubmissionBundle, canonical_json, sha256_file
from .sandbox import DockerSandbox, SandboxPolicyError, SandboxUnavailable, source_tree_digest
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
        raise RuntimeValidationError(process.stderr.strip() or "git verification failed")
    return process.stdout.strip()


def _ref_dict(ref: ArtifactRef) -> dict[str, Any]:
    return ref.as_dict()


class RuntimeService:
    def __init__(self, state_dir: Path, *, sandbox: DockerSandbox | None = None) -> None:
        self.state_dir = state_dir.resolve()
        self.store = RuntimeStore(self.state_dir)
        self.artifacts = ArtifactStore(self.state_dir / "artifacts")
        self.sandbox = sandbox or DockerSandbox()
        self.work_root = self.state_dir / "work"
        self.work_root.mkdir(parents=True, exist_ok=True)

    def submit(self, bundle: SubmissionBundle) -> tuple[JobRecord, bool]:
        self._verify_project_identity(bundle.project_profile.checkout_path, bundle.submission)
        return self.store.submit(bundle)

    def serve_once(self, *, worker_id: str = "worker-1") -> str | None:
        self._reconcile_expired_uncertain()
        accepted = self._next_job("ACCEPTED")
        if accepted is not None:
            self._prepare_job(accepted)
        claimed = self.store.claim_ready(worker_id=worker_id, now=time.time())
        if claimed is None:
            return None
        job, lease = claimed
        self._execute(job, lease)
        return job.job_id

    def _next_job(self, state: str) -> JobRecord | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE state = ? ORDER BY created_at, job_id LIMIT 1",
                (state,),
            ).fetchone()
        if row is None:
            return None
        return self.store._row_to_job(row)

    def _reconcile_expired_uncertain(self) -> None:
        now = time.time()
        with self.store._transaction() as connection:
            rows = connection.execute(
                """
                SELECT j.*, a.attempt_id
                  FROM jobs j JOIN attempts a ON a.job_id = j.job_id
                 WHERE j.state = 'EXECUTING'
                   AND a.command_started = 1
                   AND a.state NOT IN ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT')
                   AND COALESCE(a.lease_expires_at, 0) <= ?
                """,
                (now,),
            ).fetchall()
            for row in rows:
                result = {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "terminal_state": "BLOCKED",
                    "reason": "ABANDONED_UNCERTAIN",
                    "attempt_id": row["attempt_id"],
                    "automatic_reexecution": False,
                }
                connection.execute(
                    "UPDATE attempts SET state = 'ABANDONED_UNCERTAIN', updated_at = ? WHERE attempt_id = ?",
                    (now, row["attempt_id"]),
                )
                connection.execute(
                    """
                    UPDATE jobs SET state = 'BLOCKED', revision = revision + 1,
                           result_json = ?, updated_at = ? WHERE job_id = ?
                    """,
                    (canonical_json(result), now, row["job_id"]),
                )
                self.store._append_event(
                    connection,
                    row["job_id"],
                    event_type="UNCERTAIN_EXECUTION_BLOCKED",
                    state="BLOCKED",
                    payload=result,
                    created_at=now,
                )

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
        submission = job.submission
        project_path = Path(submission["resolved"]["checkout_path"])
        self._verify_project_identity(project_path, submission["submission"])
        before_digest = source_tree_digest(project_path)
        self.store.transition(
            job.job_id,
            expected_revision=job.revision,
            new_state="READY_TO_EXECUTE",
            event_type="PREFLIGHT_VERIFIED",
            payload={"project_source_digest": before_digest},
        )

    @staticmethod
    def _verify_project_identity(project_path: Path, submission: dict[str, Any]) -> None:
        expected_commit = str(submission["commit_sha"])
        expected_repository = str(submission["project_repository"])
        head = _git(project_path, "rev-parse", "HEAD")
        if head != expected_commit:
            raise RuntimeValidationError("project checkout HEAD does not match pinned commit")
        remote = _git(project_path, "remote", "get-url", "origin")
        if remote != expected_repository:
            raise RuntimeValidationError("project checkout origin does not match submission repository")

    def _execute(self, job: JobRecord, lease: AttemptLease) -> None:
        payload = job.submission
        project_path = Path(payload["resolved"]["checkout_path"])
        image = str(payload["resolved"]["execution_image"])
        selected = tuple(str(value) for value in payload["resolved"]["selected_node_ids"])
        required = tuple(str(value) for value in payload["resolved"]["required_node_ids"])
        scratch = (self.work_root / lease.attempt_id).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        before_digest = source_tree_digest(project_path)
        self.sandbox.ensure_available(image)

        command_manifest = self.sandbox.command_manifest(
            image=image,
            project_path=project_path,
            selected_node_ids=selected,
            attempt_id=lease.attempt_id,
        )
        command_ref = self.artifacts.put_json(command_manifest)
        command_manifest["artifact"] = _ref_dict(command_ref)
        lease = self.store.mark_command_started(lease, command_manifest, now=time.time())

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

        artifact_refs = self._capture_attempt_artifacts(scratch, run.stdout, run.stderr)
        artifact_refs.insert(0, command_ref)
        artifact_index = [_ref_dict(ref) for ref in artifact_refs]

        if run.cancelled:
            if run.cleanup_verified:
                result = {
                    "verdict": "CANCELLED",
                    "terminal_state": "CANCELLED",
                    "reason": "durable cancellation observed and Docker process tree removed",
                    "cleanup_verified": True,
                    "artifacts": artifact_index,
                }
                self._finish(job.job_id, lease, result, attempt_state="CANCELLED")
            else:
                result = {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "terminal_state": "BLOCKED",
                    "reason": "cancellation requested but process cleanup could not be verified",
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

        meta = self._load_json_file(scratch / "entry-meta.json")
        collection = self._load_json_file(scratch / "collection.json")
        collected = tuple(str(value) for value in collection.get("node_ids", []))
        execution_code_raw = meta.get("execution_exit_code")
        execution_code = int(execution_code_raw) if execution_code_raw is not None else int(run.exit_code)
        infrastructure_error = None
        if int(run.exit_code) == 125:
            infrastructure_error = "Docker runtime rejected or failed to start the governed execution"

        verification = verify_attempt(
            VerificationInput(
                required_node_ids=required,
                collected_node_ids=collected,
                runtime_report_path=scratch / "runtime-report.jsonl",
                command_exit_code=execution_code,
                artifact_refs=tuple(_ref_dict(ref) for ref in artifact_refs),
                product_source_unchanged=before_digest == after_digest,
                cleanup_verified=run.cleanup_verified,
                infrastructure_error=infrastructure_error,
            ),
            self.artifacts,
        )
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
        self._finish(
            job.job_id,
            lease,
            result,
            attempt_state="COMPLETED" if verification.terminal_state == "SUCCEEDED" else "FAILED",
        )

    def _finish(
        self,
        job_id: str,
        lease: AttemptLease,
        result: dict[str, Any],
        *,
        attempt_state: str,
    ) -> None:
        evidence_manifest = {
            "schema_version": 1,
            "job_id": job_id,
            "attempt_id": lease.attempt_id,
            "verdict": result["verdict"],
            "terminal_state": result["terminal_state"],
            "artifacts": result.get("artifacts", []),
        }
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
            payload={"verdict": result["verdict"], "attempt_id": lease.attempt_id},
            result=result,
            lease_token=lease.lease_token,
            now=now,
        )

    def _capture_attempt_artifacts(
        self,
        scratch: Path,
        docker_stdout: str,
        docker_stderr: str,
    ) -> list[ArtifactRef]:
        refs = [
            self.artifacts.put_text(docker_stdout),
            self.artifacts.put_text(docker_stderr),
        ]
        text_files = (
            "collection.stdout.txt",
            "collection.stderr.txt",
            "execution.stdout.txt",
            "execution.stderr.txt",
        )
        for name in text_files:
            path = scratch / name
            if path.is_file():
                refs.append(self.artifacts.put_text(path.read_text(encoding="utf-8", errors="replace")))
        typed_files = {
            "collection.json": "application/json",
            "entry-meta.json": "application/json",
            "runtime-report.jsonl": "application/x-ndjson",
            "junit.xml": "application/xml",
        }
        for name, media_type in typed_files.items():
            path = scratch / name
            if path.is_file():
                refs.append(self.artifacts.put_file(path, media_type=media_type))
        return refs

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _attempt_timeout_seconds(payload: dict[str, Any]) -> float:
        budget_ref = payload.get("bindings", {}).get("budget", {})
        _ = budget_ref
        return 15 * 60
