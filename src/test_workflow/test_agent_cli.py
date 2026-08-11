from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated, Any

import typer

from .beta_runtime.models import ManifestError, load_submission_bundle
from .beta_runtime.runtime import RuntimeService, RuntimeValidationError
from .beta_runtime.sandbox import SandboxPolicyError, SandboxUnavailable
from .beta_runtime.store import JobConflictError, RuntimeStore

app = typer.Typer(help="Durable Test Agent runtime for governed test packs.")
job_app = typer.Typer(help="Submit and inspect durable Test Agent jobs.")
runtime_app = typer.Typer(help="Operate the single-node durable worker runtime.")
app.add_typer(job_app, name="job")
app.add_typer(runtime_app, name="runtime")

StateDir = Annotated[Path, typer.Option("--state-dir", help="Persistent BETA-A state directory")]
JsonMode = Annotated[bool, typer.Option("--json", help="Emit stable JSON output")]


def _emit(value: Any, *, json_mode: bool) -> None:
    if json_mode:
        typer.echo(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            typer.echo(f"{key}: {item}")
    else:
        typer.echo(str(value))


def _job_payload(record: Any) -> dict[str, Any]:
    return {
        "job_id": record.job_id,
        "state": record.state,
        "revision": record.revision,
        "cancel_requested": record.cancel_requested,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@job_app.command("submit")
def submit_job(
    manifest: Annotated[Path, typer.Argument(help="Submission manifest YAML")],
    state_dir: StateDir,
    json_mode: JsonMode = False,
) -> None:
    try:
        bundle = load_submission_bundle(manifest)
        record, created = RuntimeService(state_dir).submit(bundle)
    except (ManifestError, RuntimeValidationError, JobConflictError) as exc:
        _emit({"error": type(exc).__name__, "message": str(exc)}, json_mode=json_mode)
        raise typer.Exit(code=2) from exc
    payload = _job_payload(record)
    payload["created"] = created
    payload["accepted_is_success"] = False
    _emit(payload, json_mode=json_mode)


@job_app.command("status")
def job_status(
    job_id: Annotated[str, typer.Argument()],
    state_dir: StateDir,
    json_mode: JsonMode = False,
) -> None:
    try:
        record = RuntimeStore(state_dir).get_job(job_id)
    except KeyError as exc:
        _emit({"error": "JOB_NOT_FOUND", "job_id": job_id}, json_mode=json_mode)
        raise typer.Exit(code=4) from exc
    _emit(_job_payload(record), json_mode=json_mode)


@job_app.command("events")
def job_events(
    job_id: Annotated[str, typer.Argument()],
    state_dir: StateDir,
    json_mode: JsonMode = False,
) -> None:
    store = RuntimeStore(state_dir)
    try:
        store.get_job(job_id)
    except KeyError as exc:
        _emit({"error": "JOB_NOT_FOUND", "job_id": job_id}, json_mode=json_mode)
        raise typer.Exit(code=4) from exc
    _emit({"job_id": job_id, "events": store.events(job_id)}, json_mode=json_mode)


@job_app.command("result")
def job_result(
    job_id: Annotated[str, typer.Argument()],
    state_dir: StateDir,
    json_mode: JsonMode = False,
) -> None:
    try:
        record = RuntimeStore(state_dir).get_job(job_id)
    except KeyError as exc:
        _emit({"error": "JOB_NOT_FOUND", "job_id": job_id}, json_mode=json_mode)
        raise typer.Exit(code=4) from exc
    if record.result is None:
        _emit(
            {
                "job_id": job_id,
                "state": record.state,
                "result_ready": False,
                "message": "deterministic verdict is not ready",
            },
            json_mode=json_mode,
        )
        raise typer.Exit(code=3)
    _emit(
        {"job_id": job_id, "state": record.state, "result_ready": True, "result": record.result},
        json_mode=json_mode,
    )


@job_app.command("cancel")
def cancel_job(
    job_id: Annotated[str, typer.Argument()],
    state_dir: StateDir,
    json_mode: JsonMode = False,
) -> None:
    try:
        record = RuntimeStore(state_dir).request_cancel(job_id)
    except KeyError as exc:
        _emit({"error": "JOB_NOT_FOUND", "job_id": job_id}, json_mode=json_mode)
        raise typer.Exit(code=4) from exc
    payload = _job_payload(record)
    payload["message"] = (
        "existing terminal truth returned"
        if record.result is not None
        else "cancellation requested; terminal CANCELLED requires cleanup proof"
    )
    _emit(payload, json_mode=json_mode)


@runtime_app.command("serve")
def serve_runtime(
    state_dir: StateDir,
    once: Annotated[bool, typer.Option("--once", help="Process at most one available job")] = False,
    worker_id: Annotated[str, typer.Option("--worker-id")] = "worker-1",
    poll_seconds: Annotated[float, typer.Option("--poll-seconds", min=0.1, max=30.0)] = 1.0,
    json_mode: JsonMode = False,
) -> None:
    service = RuntimeService(state_dir)
    try:
        if once:
            processed = service.serve_once(worker_id=worker_id)
            _emit({"processed_job_id": processed}, json_mode=json_mode)
            return
        _emit({"runtime": "started", "worker_id": worker_id}, json_mode=json_mode)
        while True:
            processed = service.serve_once(worker_id=worker_id)
            if processed is None:
                time.sleep(poll_seconds)
    except (SandboxUnavailable, SandboxPolicyError, RuntimeValidationError) as exc:
        _emit({"error": type(exc).__name__, "message": str(exc)}, json_mode=json_mode)
        raise typer.Exit(code=5) from exc


if __name__ == "__main__":
    app()
