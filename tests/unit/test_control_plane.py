from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from test_workflow.control_plane import compile_init_script, compile_storage_state
from test_workflow.specs import (
    BrowserStorageSeed,
    ClockSpec,
    DataSeedSpec,
    EnvironmentSpec,
)


def test_compile_storage_state_serializes_structured_values(tmp_path: Path) -> None:
    seed = DataSeedSpec(
        browser_storage=[
            BrowserStorageSeed(
                origin="http://todomvc.local",
                local_storage={"todos": [{"id": 1, "completed": False}]},
            )
        ]
    )
    output = compile_storage_state(seed, tmp_path / "storage.json")
    payload = json.loads(output.read_text())
    stored = payload["origins"][0]["localStorage"][0]["value"]
    assert json.loads(stored) == [{"id": 1, "completed": False}]


def test_compile_init_script_controls_time_and_randomness(tmp_path: Path) -> None:
    environment = EnvironmentSpec(
        profile="isolated",
        base_url="http://todomvc.local",
        clock=ClockSpec(frozen_at=datetime.fromisoformat("2026-08-04T20:00:00+08:00")),
        random_seed=42,
        data_seed_path="environment/data-seed.yaml",
        mock_plan_path="environment/mock-plan.yaml",
    )
    output = compile_init_script(environment, tmp_path / "init.js")
    script = output.read_text()
    assert "2026-08-04T20:00:00+08:00" in script
    assert "1664525" in script
    assert "Date = ControlledDate" in script
