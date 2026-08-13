from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_REPORT_PATH = Path(os.environ.get("BETA_A_RUNTIME_REPORT", "/evidence/runtime-report.jsonl"))


def _append(value: dict[str, Any]) -> None:
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _REPORT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def pytest_runtest_logreport(report: Any) -> None:
    _append(
        {
            "nodeid": str(report.nodeid),
            "when": str(report.when),
            "outcome": str(report.outcome),
        }
    )
