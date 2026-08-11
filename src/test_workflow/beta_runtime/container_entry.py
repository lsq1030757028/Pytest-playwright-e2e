from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

EVIDENCE_DIR = Path("/evidence")
INPUT_PATH = EVIDENCE_DIR / "command-input.json"
COLLECTION_JSON = EVIDENCE_DIR / "collection.json"
COLLECTION_STDOUT = EVIDENCE_DIR / "collection.stdout.txt"
COLLECTION_STDERR = EVIDENCE_DIR / "collection.stderr.txt"
EXECUTION_STDOUT = EVIDENCE_DIR / "execution.stdout.txt"
EXECUTION_STDERR = EVIDENCE_DIR / "execution.stderr.txt"
JUNIT_PATH = EVIDENCE_DIR / "junit.xml"
RUNTIME_REPORT = EVIDENCE_DIR / "runtime-report.jsonl"
META_PATH = EVIDENCE_DIR / "entry-meta.json"

_current_process: subprocess.Popen[str] | None = None
_cancel_requested = False


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _forward_termination(signum: int, _frame: Any) -> None:
    global _cancel_requested
    _cancel_requested = True
    process = _current_process
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        return


def _run(argv: list[str]) -> tuple[int, str, str]:
    global _current_process
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "/runtime",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "BETA_A_RUNTIME_REPORT": str(RUNTIME_REPORT),
            "HOME": "/tmp/beta-a-home",
        },
    )
    _current_process = process
    stdout, stderr = process.communicate()
    _current_process = None
    return int(process.returncode), stdout, stderr


def _collected_node_ids(stdout: str) -> list[str]:
    nodes: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if "::" in line and not line.startswith(("=", "<", ">")):
            nodes.append(line)
    return list(dict.fromkeys(nodes))


def main() -> int:
    signal.signal(signal.SIGTERM, _forward_termination)
    signal.signal(signal.SIGINT, _forward_termination)
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    nodes = payload["selected_node_ids"]
    if not isinstance(nodes, list) or not nodes:
        _write_json(META_PATH, {"error": "selected_node_ids is empty"})
        return 4

    collection_argv = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--collect-only",
        "-q",
        *nodes,
    ]
    collection_code, collection_out, collection_err = _run(collection_argv)
    _write_text(COLLECTION_STDOUT, collection_out)
    _write_text(COLLECTION_STDERR, collection_err)
    collected = _collected_node_ids(collection_out)
    _write_json(COLLECTION_JSON, {"node_ids": collected, "exit_code": collection_code})

    meta: dict[str, Any] = {
        "collection_exit_code": collection_code,
        "execution_exit_code": None,
        "cancel_requested": _cancel_requested,
    }
    if _cancel_requested:
        _write_json(META_PATH, meta)
        return 130
    if collection_code != 0:
        _write_json(META_PATH, meta)
        return collection_code

    execution_argv = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-p",
        "beta_a_pytest_plugin",
        f"--junitxml={JUNIT_PATH}",
        "-q",
        *nodes,
    ]
    execution_code, execution_out, execution_err = _run(execution_argv)
    _write_text(EXECUTION_STDOUT, execution_out)
    _write_text(EXECUTION_STDERR, execution_err)
    meta["execution_exit_code"] = execution_code
    meta["cancel_requested"] = _cancel_requested
    _write_json(META_PATH, meta)
    if _cancel_requested:
        return 130
    return execution_code


if __name__ == "__main__":
    raise SystemExit(main())
